# 🕵️‍♂️ SharlokInsta - OSINT & Profile Scraper (Desktop)

Ferramenta automatizada para extração e download completo de dados públicos e privados autorizados no Instagram, simulando 100% a navegação do Google Chrome Desktop no Windows através do Playwright.

---

## ⚡ Recursos

- **📸 Feed Completo:** Download de todas as fotos em alta resolução (1080x1080 via `srcset`).
- **🌟 Destaques (Highlights):** Mapeamento e download de todos os slides (fotos e vídeos `.mp4`).
- **⏱️ Stories Ativos (24h):** Captura automática de postagens de stories vigentes.
- **📝 Biografia & Metadados:** Exportação da foto de avatar em HD, contadores (posts, seguidores, seguindo), bio completa com emojis e separação de links externos em `bio.txt` e `dados_perfil.json`.
- **🎯 Gestão de Alvos:** Sistema para seguir e monitorar solicitações de perfis privados com download automático assim que a solicitação for aceita.
- **🔒 Seguro & Modular:** Credenciais protegidas via arquivo `.env` (nunca sobem para o GitHub).

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
- **`[1]`** 🎯 Enviar Solicitação para Alvo Privado
- **`[2]`** 🔄 Verificar Solicitações e Baixar Conteúdo Aceito
- **`[3]`** 📥 Baixar Perfil Aberto/Aprovado Agora (Feed, Destaques, Stories, Bio)
- **`[4]`** 📋 Ver Histórico de Alvos Monitorados
- **`[5]`** 🔑 Configurar Conta / Atualizar SessionID
- **`[0]`** 🚪 Sair

Os downloads ficam salvos organizados por usuário em:
`downloads/@<username>/`
