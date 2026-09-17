# 🕵️‍♂️ SharlokInsta - OSINT & Profile Scraper (Desktop)

Ferramenta automatizada para extração e download completo de dados públicos e privados autorizados no Instagram, simulando 100% a navegação do Google Chrome Desktop no Windows através do Playwright.

---

## ⚡ Recursos Principais

- **📸 Feed Completo:** Download de todas as fotos em alta resolução (1080x1080 via `srcset`).
- **🌟 Destaques (Highlights):** Mapeamento e download de todos os slides (fotos e vídeos `.mp4`).
- **⏱️ Stories Ativos (24h):** Captura automática de postagens de stories vigentes.
- **📝 Biografia & Metadados:** Exportação da foto de avatar em HD, contadores (posts, seguidores, seguindo), bio completa com emojis e separação de links externos em `bio.txt` e `dados_perfil.json`.
- **👥 Pool de Múltiplas Contas:** Gerencie 2 ou mais contas fantoches com seus respectivos Session IDs salvos com segurança.
- **🔄 Cascata Inteligente de Rejeição:** Se uma conta tiver a solicitação recusada pelo alvo, o bot entra em **cooldown de 2 horas** e automaticamente transfere a abordagem para a próxima conta ativa do pool!
- **👁️ Modo Sentinela (24/7):** Loop contínuo em segundo plano que monitora aprovações, baixas automáticas e rotação de contas sem intervenção manual.
- **🔒 Seguro & Modular:** Credenciais protegidas via arquivos locais `.env` e `contas_pool.json` (bloqueados no `.gitignore` para nunca subirem ao GitHub).

---

## 🚀 Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/SamuelBarbosa1/SharlokInsta.git
   cd SharlokInsta
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure suas variáveis de ambiente:**
   Copie o template `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```
   Abra o arquivo `.env` e preencha com as credenciais da sua conta do Instagram obtidas via cookies de navegador (ex: extensão *Cookie-Editor* no Chrome Desktop):
   ```env
   IG_USER=seu_usuario
   IG_DS_USER_ID=seu_user_id
   IG_SESSIONID=seu_sessionid_aqui
   ```

---

## 💻 Como Usar

Execute o arquivo principal:
```bash
python main.py
```

### Menu de Opções:
- **`[1]`** 🎯 **Enviar Solicitação para Alvo Privado & Monitorar:** Escolha qual conta do pool abordará o alvo e inicie o acompanhamento.
- **`[2]`** 🔄 **Verificar Solicitações & Cascata de Rejeição:** Checa aprovações, executa downloads automáticos e aciona a troca de contas em caso de recusa após o cooldown.
- **`[3]`** ⚡ **Baixar Perfil Agora:** Download imediato de qualquer perfil já aceito ou público (Feed, Destaques, Stories, Bio).
- **`[4]`** 📋 **Ver Histórico de Alvos e Status da Cascata:** Visualize o status de cada alvo, conta atual responsável, tentativas e tempo de cooldown.
- **`[5]`** 👥 **Gerenciar Pool de Contas:** Adicione uma 2ª ou 3ª conta fantoche, ative/desative contas e teste o login das sessões.
- **`[6]`** 👁️ **Iniciar Modo Sentinela (Loop Automático 24/7):** Deixe o robô monitorando sozinho em segundo plano (com intervalo configurável, ex: 30 minutos).
- **`[0]`** 🚪 **Sair**

Os downloads ficam salvos organizados por usuário em:
`downloads/@<username>/`
