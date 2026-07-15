# 🌱 Verificador de Estoque Automatizado - Associação de Pacientes

Este é um script em Python desenvolvido para monitorar a disponibilidade de flores e concentrados medicinais no chatbot de uma associação de pacientes. O script consulta as APIs públicas do bot, processa as respostas textuais em busca de produtos e preços, compara os resultados com uma varredura anterior para identificar alterações no estoque e envia notificações em tempo real.

> [!WARNING]
> **AVISO IMPORTANTE DE FINS EDUCACIONAIS**
> Este projeto foi desenvolvido exclusivamente para fins de estudo de integração de APIs, raspagem de dados estruturados a partir de chatbots (Typebot) e envio de notificações automatizadas.
> * **Não** possui fins lucrativos.
> * **Não** realiza compras automatizadas ou interfere no funcionamento do serviço da associação.
> * **Não** é afiliado, mantido ou patrocinado por qualquer associação de pacientes.
> * O uso deste script é de inteira responsabilidade do usuário. Recomenda-se usá-lo com moderação para evitar sobrecarga desnecessária aos servidores da API.

---

## ✨ Funcionalidades

- 🔄 **Consulta Automatizada**: Inicia e segue o fluxo do chatbot da associação para obter a listagem de flores e concentrados.
- ⚡ **Alta Performance (Concorrência)**: Consultas simultâneas de flores e concentrados (via `ThreadPoolExecutor`) para otimizar a velocidade de execução.
- 🔍 **Extração Inteligente (Regex)**: Analisa o texto formatado do bot e extrai nomes e preços corretos dos produtos.
- 📋 **Detalhamento de Strains/Concentrados**: Opção para buscar informações completas (descrição, terpenos, genética, imagem) de cada item e salvá-las localmente.
- 🛡️ **Bypass de Avisos**: Detecta e aceita automaticamente os termos de aviso/consentimento durante a interação com o bot (como botões "ciente").
- 📊 **Histórico Local**: Mantém um cache das últimas 50 consultas em `estoque_historico.json`.
- 🆚 **Comparação de Estoques**: Detecta e exibe no terminal se houve:
  - 🟢 Novos itens adicionados.
  - 🟡 Alteração de preços.
  - 🔴 Produtos esgotados.
- 🔔 **Notificações Integradas**:
  - **ntfy.sh**: Envia notificações push diretamente para o seu celular (gratuito e sem necessidade de criar contas).
  - **Telegram Bot**: Envia mensagens em um chat ou canal do Telegram.
- 🕒 **Modo Monitoramento (Loop)**: Permite deixar o script rodando em segundo plano de forma contínua com intervalo configurável.

---

## 🛠️ Pré-requisitos

- **Python 3.8** ou superior.
- Biblioteca `requests` instalada.

---

## 🚀 Como Usar

### 1. Clonar ou Baixar o Repositório
Baixe os arquivos para sua máquina local.

### 2. Instalar as Dependências
Abra o terminal na pasta do projeto e execute:
```bash
pip install requests
```

### 3. Configurar as Variáveis de Ambiente
Para evitar expor seus dados pessoais (como CPF e tokens) publicamente no GitHub:

1. Faça uma cópia do arquivo `.env.example` e renomeie-a para `.env`:
   ```bash
   cp .env.example .env
   ```
2. Abra o arquivo `.env` e preencha as variáveis:
   - `BOT_CPF`: O CPF do paciente cadastrado e autorizado.
   - `BOT_BASE_URL`: URL base da API do bot (ex: `https://[DOMINIO_DO_BOT]/api/v1`).
   - `BOT_REFERER`: URL referer do chatbot (ex: `https://[DOMINIO_DO_BOT]/`).
   - `BOT_TYPEBOT_ID`: (Opcional) O ID do fluxo de chat (padrão: `pix-pagamento`). Se a associação alterar a versão do bot, você pode atualizar esse ID aqui sem mexer no código.
   - `NTFY_TOPIC`: (Opcional) Tópico de sua preferência no aplicativo ntfy.
   - `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`: (Opcional) Tokens para envio de mensagens via Telegram.

> [!IMPORTANT]
> O arquivo `.env` já está configurado no `.gitignore` para que suas informações pessoais nunca sejam enviadas para o seu repositório do GitHub.

### 4. Executar o Script

#### Execução Única (Scan Rápido):
```bash
python verificar_estoque.py
```

#### Modo Monitoramento Contínuo (Loop):
O script verificará o estoque periodicamente. Por padrão, a cada 1 hora (3600 segundos).
```bash
python verificar_estoque.py --loop
```

Você também pode personalizar o intervalo (em segundos):
```bash
# Executa a varredura a cada 30 minutos (1800 segundos)
python verificar_estoque.py --loop --interval 1800
```

#### Buscar e Salvar Detalhes Completos (Strains/Concentrados):
Se quiser buscar informações detalhadas sobre a genética, descrição aromática, terpenos predominantes e a imagem de cada strain ou concentrado disponível:
```bash
python verificar_estoque.py --detalhes
```
*Esta opção salva os dados detalhados no arquivo `detalhes_produtos.json` e os exibe de forma formatada no terminal.*

#### Passando o CPF via Linha de Comando:
Se preferir não usar o arquivo `.env` para o CPF, você pode passá-lo diretamente como argumento (embora o `.env` seja mais seguro):
```bash
python verificar_estoque.py --cpf 12345678900
```

---

## ⚙️ Configuração de Notificações

### 📲 Opção 1: Notificações pelo ntfy.sh (Recomendado & Mais Simples)
1. Instale o aplicativo **ntfy** no seu celular (disponível na App Store do iOS e Google Play do Android).
2. Escolha um nome de tópico aleatório e exclusivo (ex: `estoque_monitor_murilo_987`).
3. Adicione esse tópico no app ntfy clicando em **Subscribe to topic**.
4. Defina esse mesmo nome na variável `NTFY_TOPIC` no arquivo `.env`.
5. Pronto! Sempre que houver mudanças, você receberá um push grátis no celular.

### 💬 Opção 2: Notificações pelo Telegram
1. Fale com o `@BotFather` no Telegram e digite `/newbot` para criar um bot. Salve o **HTTP API Token** fornecido.
2. Inicie uma conversa com seu bot recém-criado digitando qualquer mensagem.
3. Fale com o bot `@userinfobot` no Telegram para descobrir o seu **Chat ID** numérico.
4. Preencha `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no arquivo `.env`.

---

## ⚠️ O que fazer se o Bot mudar de ID?

O script consome a API do chatbot hospedado pela associação. Se a associação publicar uma nova versão do bot com um ID diferente (ex: mudar de `pix-pagamento` para outro nome), o script pode começar a falhar retornando erros de conexão ou de sessão (como `404 Not Found`).

Para corrigir isso sem alterar o código Python:
1. Acesse o site do chatbot de atendimento.
2. Abra a aba de ferramentas do desenvolvedor do navegador (tecla `F12` ou clique com o botão direito -> **Inspecionar**) e acesse a aba **Rede** (Network).
3. Digite `startChat` ou `sessions` no campo de filtro/busca.
4. Atualize a página. No painel de requisições de rede, você verá uma requisição HTTP para uma URL parecida com:
   `https://[DOMINIO_DO_BOT]/api/v1/typebots/NOME_DO_BOT/startChat`
5. Copie a parte correspondente ao `NOME_DO_BOT` (ex: `pix-pagamento`) e configure-o no seu arquivo `.env`:
   ```env
   BOT_TYPEBOT_ID=novo-nome-do-bot-aqui
   ```

