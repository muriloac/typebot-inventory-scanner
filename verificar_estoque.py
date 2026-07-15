import requests
import json
import re
import sys
import time
import os
from datetime import datetime

# Reconfigure stdout to support UTF-8 formatting (essential for Windows terminal)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ANSI colors for styling the terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Carregar variáveis de ambiente de um arquivo .env se ele existir
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# Configurações do Bot carregadas das variáveis de ambiente / .env
BASE_URL = os.environ.get("BOT_BASE_URL", "")
REFERER_URL = os.environ.get("BOT_REFERER", "")
TYPEBOT_ID = os.environ.get("BOT_TYPEBOT_ID", "pix-pagamento")
HISTORY_FILE = "estoque_historico.json"

# Configurações sensíveis e de notificação carregadas das variáveis de ambiente / .env
DEFAULT_CPF = os.environ.get("BOT_CPF", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def extract_rich_text(node):
    """Recursively extract and format text from Typebot richText structures."""
    if not node:
        return ""
    if isinstance(node, list):
        return "".join(extract_rich_text(item) for item in node)
    if isinstance(node, dict):
        node_type = node.get("type")
        children = node.get("children", [])
        
        if node_type == "p":
            return "".join(extract_rich_text(c) for c in children) + "\n"
        elif node_type == "li":
            return "- " + "".join(extract_rich_text(c) for c in children).strip() + "\n"
        elif node_type == "lic":
            return "".join(extract_rich_text(c) for c in children)
        elif node_type == "ul":
            return "".join(extract_rich_text(c) for c in children)
            
        if "text" in node:
            return node["text"]
            
        parts = []
        for val in node.values():
            if isinstance(val, (dict, list)):
                res = extract_rich_text(val)
                if res:
                    parts.append(res)
        return "".join(parts)
    return ""

class BotScanner:
    def __init__(self, cpf=DEFAULT_CPF):
        self.cpf = cpf

    def _create_session(self):
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Referer": REFERER_URL
        })
        return session

    def _send_msg(self, session, session_id, text):
        url = f"{BASE_URL}/sessions/{session_id}/continueChat"
        res = session.post(url, json={"message": {"type": "text", "text": text}})
        res.raise_for_status()
        return res.json()

    def _send_msg_handle_warnings(self, session, session_id, text):
        data = self._send_msg(session, session_id, text)
        while True:
            items = data.get("input", {}).get("items", [])
            warning_button = None
            for item in items:
                content = item.get("content", "")
                if content and "ciente" in content.lower():
                    warning_button = content
                    break
            
            if warning_button:
                data = self._send_msg(session, session_id, warning_button)
            else:
                break
        return data

    def _start_session(self):
        """Starts a new chat session with the bot and navigates to the main menu."""
        session = self._create_session()
        r = session.post(f"{BASE_URL}/typebots/{TYPEBOT_ID}/startChat", json={
            "isStreamEnabled": False,
            "prefilledVariables": {},
            "isOnlyRegistering": False
        })
        r.raise_for_status()
        data = r.json()
        session_id = data.get("sessionId")

        max_steps = 10
        for _ in range(max_steps):
            items = data.get("input", {}).get("items", [])
            input_type = data.get("input", {}).get("type")
            
            # Check if we have reached the main menu
            is_main_menu = False
            for item in items:
                content = item.get("content", "")
                if content and ("adquirir flores" in content.lower() or "adquirir concentrados" in content.lower()):
                    is_main_menu = True
                    break
            
            if is_main_menu:
                return session_id, data, session
                
            # If not main menu, determine what to send
            if input_type == "text input":
                data = self._send_msg(session, session_id, self.cpf)
            elif input_type == "choice input":
                chosen_content = None
                for item in items:
                    content = item.get("content", "")
                    if content and ("sou paciente" in content.lower() or "ciente" in content.lower()):
                        chosen_content = content
                        break
                if not chosen_content and items:
                    chosen_content = items[0].get("content")
                
                if chosen_content:
                    data = self._send_msg(session, session_id, chosen_content)
                else:
                    raise Exception("No choices found in choice input step.")
            else:
                raise Exception(f"Unexpected input type: {input_type}")
                
        raise Exception("Failed to reach main menu within max steps.")

    def get_stock(self):
        """Queries all categories and gathers the complete stock details."""
        from concurrent.futures import ThreadPoolExecutor
        
        stock = {
            "flores": [],
            "concentrados": [],
            "oleos": []
        }

        def fetch_flores():
            try:
                session_id, _, session = self._start_session()
                data = self._send_msg_handle_warnings(session, session_id, "Quero adquirir flores!")
                
                # Extract rich text which contains the formatted list of flowers
                msgs = data.get("messages", [])
                text_content = extract_rich_text(msgs)
                
                # Use regex to parse lines like: "- Wedding Cake (indoor) - R$ 75.00"
                matches = re.findall(r"-\s*([^-\n]+?)\s*-\s*R\$\s*([\d.,]+)", text_content)
                res = []
                for name, price in matches:
                    res.append({
                        "nome": name.strip(),
                        "preco": float(price.replace(",", "."))
                    })
                return res
            except Exception as e:
                print(f"{RED}Erro ao consultar flores: {e}{RESET}")
                return []

        def fetch_concentrados():
            try:
                session_id, _, session = self._start_session()
                data = self._send_msg_handle_warnings(session, session_id, "Quero adquirir concentrados!")
                
                # Check if there are select choices or if it says out of stock
                items = data.get("input", {}).get("items", [])
                msgs = data.get("messages", [])
                text_content = extract_rich_text(msgs)
                
                res = []
                # If the response indicates out of stock, we record empty list
                if "sem disponibilidade" not in text_content.lower() and items:
                    # Try to parse from the text content first (which contains names and prices)
                    matches = re.findall(r"-\s*([^-\n]+?)\s*-\s*R\$\s*([\d.,]+)", text_content)
                    if matches:
                        for name, price in matches:
                            res.append({
                                "nome": name.strip(),
                                "preco": float(price.replace(",", "."))
                            })
                    else:
                        # Fallback to items if no matches in text (avoiding categories like THC/CBD/VOLTAR)
                        for item in items:
                            content = item.get("content", "")
                            if (content and 
                                content.upper() not in ["VOLTAR", "THC", "CBD"] and 
                                "óleo" not in content.lower() and 
                                "flores" not in content.lower()):
                                res.append({"nome": content})
                return res
            except Exception as e:
                print(f"{RED}Erro ao consultar concentrados: {e}{RESET}")
                return []

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_flores = executor.submit(fetch_flores)
            future_concentrados = executor.submit(fetch_concentrados)
            
            stock["flores"] = future_flores.result()
            stock["concentrados"] = future_concentrados.result()

        return stock

    def get_details(self):
        """Queries the details of all available products (flores and concentrados)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        categories = {
            "flores": "Quero adquirir flores!",
            "concentrados": "Quero adquirir concentrados!"
        }
        
        product_list = []

        # 1. Discover all subcategories and product names
        for cat_key, cat_msg in categories.items():
            try:
                session_id, data, session = self._start_session()
                data = self._send_msg_handle_warnings(session, session_id, cat_msg)
                
                subcats = [
                    item.get("content") for item in data.get("input", {}).get("items", [])
                    if item.get("content") and item.get("content").upper() not in ["VOLTAR", "CONTINUAR"]
                ]
                
                for subcat in subcats:
                    sub_sess_id, _, sub_sess = self._start_session()
                    data = self._send_msg_handle_warnings(sub_sess, sub_sess_id, cat_msg)
                    sub_data = self._send_msg_handle_warnings(sub_sess, sub_sess_id, subcat)
                    
                    prods = [
                        item.get("content") for item in sub_data.get("input", {}).get("items", [])
                        if item.get("content") and item.get("content").upper() not in ["VOLTAR", "CONTINUAR"]
                    ]
                    for prod_name in prods:
                        product_list.append({
                            "category": cat_key,
                            "subcategory": subcat,
                            "name": prod_name
                        })
            except Exception as e:
                print(f"{RED}Erro ao listar produtos para {cat_key}: {e}{RESET}")

        def parse_messages(messages):
            text_parts = []
            image_url = None
            for msg in messages:
                msg_type = msg.get("type")
                content = msg.get("content", {})
                if msg_type == "text":
                    text_parts.append(extract_rich_text(msg))
                elif msg_type in ["image", "embed"] and isinstance(content, dict):
                    image_url = content.get("url")
            return "\n".join(text_parts).strip(), image_url

        detailed_products = {
            "flores": [],
            "concentrados": []
        }
        
        print(f"\n{CYAN}Encontrados {len(product_list)} produtos no total. Buscando detalhes concorrentemente...{RESET}")
        
        def fetch_prod_details(prod):
            try:
                session_id, _, session = self._start_session()
                
                cat_msg = categories[prod["category"]]
                self._send_msg_handle_warnings(session, session_id, cat_msg)
                self._send_msg_handle_warnings(session, session_id, prod["subcategory"])
                prod_data = self._send_msg_handle_warnings(session, session_id, prod["name"])
                
                desc, img = parse_messages(prod_data.get("messages", []))
                
                return {
                    "category": prod["category"],
                    "data": {
                        "nome": prod["name"],
                        "subcategoria": prod["subcategory"],
                        "descricao": desc,
                        "imagem_url": img,
                        "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            except Exception as e:
                print(f"{RED}Erro ao buscar detalhes de {prod['name']}: {e}{RESET}")
                return None

        # Fetch product details concurrently with up to 5 workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_prod_details, prod): prod for prod in product_list}
            for idx, future in enumerate(as_completed(futures), 1):
                prod = futures[future]
                result = future.result()
                if result:
                    detailed_products[result["category"]].append(result["data"])
                    print(f"[{idx}/{len(product_list)}] ✓ Detalhes obtidos para: {prod['name']} ({prod['subcategory']})")
                
        return detailed_products


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(stock_data):
    history = load_history()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history[timestamp] = stock_data
    
    # Keep only the last 50 scans to save space
    if len(history) > 50:
        sorted_keys = sorted(history.keys())
        for k in sorted_keys[:-50]:
            del history[k]
            
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def get_last_stock(history):
    if not history:
        return None
    sorted_keys = sorted(history.keys())
    return history[sorted_keys[-1]]

def compare_stock(old_stock, new_stock):
    """Compares previous stock with new stock, prints colored changes, and returns list of new additions."""
    additions = []
    has_changes = False
    
    # Compare Flowers
    old_flores = {item["nome"]: item["preco"] for item in old_stock.get("flores", [])}
    new_flores = {item["nome"]: item["preco"] for item in new_stock.get("flores", [])}
    
    print(f"\n{BOLD}{CYAN}=== ALTERAÇÕES NO ESTOQUE ==={RESET}")
    
    # Flowers additions/removals/price-changes
    for name in new_flores:
        if name not in old_flores:
            msg = f"🟢 [Flores] Adicionado: {name} - R$ {new_flores[name]:.2f}"
            print(f" {GREEN}{msg}{RESET}")
            additions.append(msg)
            has_changes = True
        elif old_flores[name] != new_flores[name]:
            print(f" {YELLOW}🟡 [Flores] Preço Alterado: {name} (R$ {old_flores[name]:.2f} -> R$ {new_flores[name]:.2f}){RESET}")
            has_changes = True
            
    for name in old_flores:
        if name not in new_flores:
            print(f" {RED}🔴 [Flores] Esgotado: {name}{RESET}")
            has_changes = True

    # Compare Concentrates
    old_conc = {item["nome"]: item.get("preco") for item in old_stock.get("concentrados", [])}
    new_conc = {item["nome"]: item.get("preco") for item in new_stock.get("concentrados", [])}
    
    for name in new_conc:
        new_price = new_conc[name]
        old_price = old_conc.get(name)
        price_str = f" - R$ {new_price:.2f}" if new_price is not None else ""
        
        if name not in old_conc:
            msg = f"🟢 [Concentrados] Adicionado: {name}{price_str}"
            print(f" {GREEN}{msg}{RESET}")
            additions.append(msg)
            has_changes = True
        elif old_price != new_price and old_price is not None and new_price is not None:
            print(f" {YELLOW}🟡 [Concentrados] Preço Alterado: {name} (R$ {old_price:.2f} -> R$ {new_price:.2f}){RESET}")
            has_changes = True
            
    for name in old_conc:
        if name not in new_conc:
            print(f" {RED}🔴 [Concentrados] Esgotado: {name}{RESET}")
            has_changes = True
            
    if not has_changes:
        print(f" Sem alterações desde a última verificação.")
    print("=" * 30 + "\n")
    
    return additions

def display_current_stock(stock):
    """Prints the current stock in a clean, beautiful layout."""
    print(f"\n{BOLD}{MAGENTA}🌱 ESTOQUE ATUAL 🌱{RESET}")
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    # Flowers
    print(f"\n{BOLD}{CYAN}🌸 FLORES{RESET}")
    if stock["flores"]:
        for f in stock["flores"]:
            print(f" - {f['nome']:<40} {GREEN}R$ {f['preco']:.2f}{RESET}")
    else:
        print(" Nenhuma flor disponível.")
        
    pass

    # Concentrates
    print(f"\n{BOLD}{CYAN}🍯 CONCENTRADOS{RESET}")
    if stock["concentrados"]:
        for c in stock["concentrados"]:
            if c.get("preco") is not None:
                print(f" - {c['nome']:<40} {GREEN}R$ {c['preco']:.2f}{RESET}")
            else:
                print(f" - {c['nome']}")
    else:
        print(f" {YELLOW}Indisponível (Sem estoque){RESET}")
        
    print("\n" + "=" * 60 + "\n")

def send_notifications(changes):
    """Sends stock changes via configured channels (ntfy and/or Telegram)."""
    if not changes:
        return
        
    message = "\n".join(changes)
    
    # 1. Send via ntfy.sh
    if NTFY_TOPIC:
        try:
            url = f"https://ntfy.sh/{NTFY_TOPIC}"
            headers = {
                "Title": "Alterações de Estoque",
                "Priority": "high",
                "Tags": "herb,bell"
            }
            r = requests.post(url, data=message.encode('utf-8'), headers=headers)
            if r.status_code == 200:
                print(f"{GREEN}Notificação enviada com sucesso para o ntfy (tópico: {NTFY_TOPIC}){RESET}")
            else:
                print(f"{RED}Falha ao enviar notificação ntfy (status: {r.status_code}){RESET}")
        except Exception as e:
            print(f"{RED}Erro ao enviar notificação ntfy: {e}{RESET}")
            
    # 2. Send via Telegram Bot
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"🌱 *Alterações de Estoque*\n\n{message}",
                "parse_mode": "Markdown"
            }
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                print(f"{GREEN}Notificação enviada com sucesso para o Telegram{RESET}")
            else:
                print(f"{RED}Falha ao enviar notificação Telegram (status: {r.status_code}){RESET}")
        except Exception as e:
            print(f"{RED}Erro ao enviar notificação Telegram: {e}{RESET}")

def execute_scan(cpf):
    print(f"{CYAN}Iniciando varredura no bot...{RESET}")
    scanner = BotScanner(cpf=cpf)
    new_stock = scanner.get_stock()
    
    # Load past data to compare
    history = load_history()
    old_stock = get_last_stock(history)
    
    changes = []
    if old_stock:
        changes = compare_stock(old_stock, new_stock)
        
    display_current_stock(new_stock)
    save_history(new_stock)
    
    if changes:
        send_notifications(changes)

def execute_details_fetch(cpf):
    print(f"{CYAN}Iniciando busca detalhada das strains/concentrados...{RESET}")
    scanner = BotScanner(cpf=cpf)
    details = scanner.get_details()
    
    output_file = "detalhes_produtos.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(details, f, indent=2, ensure_ascii=False)
        print(f"\n{GREEN}✓ Detalhes das strains e concentrados salvos com sucesso em {output_file}!{RESET}")
    except Exception as e:
        print(f"{RED}Erro ao salvar detalhes em {output_file}: {e}{RESET}")
    
    # Display details summary in terminal
    print(f"\n{BOLD}{MAGENTA}🌱 DETALHES DAS STRAINS / CONCENTRADOS 🌱{RESET}")
    print("=" * 60)
    for cat in ["flores", "concentrados"]:
        print(f"\n{BOLD}{CYAN}=== {cat.upper()} ==={RESET}")
        if not details[cat]:
            print("  Nenhum detalhe encontrado.")
        for item in details[cat]:
            print(f"\n{BOLD}{GREEN}• {item['nome']} ({item['subcategoria']}){RESET}")
            if item.get("imagem_url"):
                print(f"  {YELLOW}Imagem:{RESET} {item['imagem_url']}")
            desc_lines = item['descricao'].split('\n')
            for line in desc_lines:
                if line.strip():
                    print(f"  {line.strip()}")
    print("\n" + "=" * 60 + "\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verificador de Estoque")
    parser.add_argument("--cpf", default=DEFAULT_CPF, help="CPF do paciente cadastrado")
    parser.add_argument("--loop", action="store_true", help="Executar continuamente em loop")
    parser.add_argument("--interval", type=int, default=3600, help="Intervalo do loop em segundos (padrão: 3600s / 1 hora)")
    parser.add_argument("--detalhes", action="store_true", help="Buscar e salvar detalhes (genética, terpenos, imagem) de cada strain/concentrado")
    
    args = parser.parse_args()
    
    if not args.cpf:
        print(f"{RED}Erro: CPF do paciente não configurado.{RESET}")
        print("Defina a variável BOT_CPF no arquivo .env ou forneça o CPF usando o argumento --cpf.")
        sys.exit(1)
        
    if not BASE_URL or not REFERER_URL:
        print(f"{RED}Erro: URL base (BOT_BASE_URL) ou Referer (BOT_REFERER) não configurados.{RESET}")
        print("Defina as variáveis BOT_BASE_URL e BOT_REFERER no arquivo .env.")
        sys.exit(1)
        
    if args.detalhes:
        execute_details_fetch(args.cpf)
        sys.exit(0)
        
    if args.loop:
        print(f"{GREEN}Iniciando modo monitorão contínuo (a cada {args.interval}s)...{RESET}")
        while True:
            try:
                execute_scan(args.cpf)
            except Exception as e:
                print(f"{RED}Erro durante a execução: {e}{RESET}")
            print(f"Aguardando {args.interval} segundos para a próxima verificação...\n")
            time.sleep(args.interval)
    else:
        execute_scan(args.cpf)

if __name__ == "__main__":
    main()
