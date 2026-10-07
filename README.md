# 🕵️‍♂️ SharlokInsta - OSINT & Instagram Profile Scraper (Desktop)

Ferramenta profissional e automatizada para extração e download completo de dados públicos e privados autorizados no Instagram, simulando navegação humana legítima pelo Google Chrome Desktop no Windows através do Playwright.

---

## ⚡ Recursos Principais

- **📸 Feed Completo:** Download de todas as fotos na resolução máxima (1080x1080 via `srcset`).
- **🌟 Destaques (Highlights):** Mapeamento e download de todas as pastas de destaques (fotos e vídeos `.mp4`).
- **⏱️ Stories Ativos (24h):** Captura automática de postagens de stories vigentes.
- **📝 Biografia & Metadados:** Exportação da foto de avatar em HD, contadores (posts, seguidores, seguindo), bio completa com emojis e links externos em `bio.txt` e `dados_perfil.json`.
- **👥 Pool de Múltiplas Contas Fantoches:** Gerenciamento de múltiplas contas bots com suporte a adição, alternância e teste de sessão em tempo real.
- **📂 Importação em Massa (`alvos.txt`):** Carregue uma lista de alvos em lote com distribuição automática e equilibrada entre as contas ativas (round-robin).
- **🛡️ Proteção Anti-Spam:** Intervalos randômicos humanizados entre envios em massa (5 a 10 segundos) para prevenir bloqueios.
- **🔄 Cascata Inteligente de Recusa & Vácuo:** Se uma conta for rejeitada ou deixada no vácuo (sem resposta pelo prazo limite), o robô cancela a solicitação pendente no perfil e sorteia aleatoriamente outra conta fantoche do pool para continuar a abordagem.
- **👁️ Modo Sentinela (24/7):** Loop contínuo em segundo plano que monitora aceites, executa downloads imediatos e coordena rotações de bots sem necessidade de intervenção humana.
- **🔒 Seguro & Modular:** Arquitetura limpa e desacoplada (`core/`, `scraper/`, `flows/`). Credenciais e dados são mantidos exclusivamente em arquivos locais e protegidos no `.gitignore`.

---

## 📁 Estrutura do Projeto

```text
SharlokInsta/
│
├── core/                         # Gestão de dados, storage e configurações
│   ├── config.py                 # .env, constantes (COOLDOWN, TIMEOUT), arquivos locais
│   ├── database.py               # SQLite (osint_coletas.db) e registro de coletas
│   ├── pool.py                   # Gestão do pool de múltiplas contas (contas_pool.json)
│   └── targets.py                # Gestão de alvos e importação em massa (alvos_monitorados.json)
│
├── scraper/                      # Automação e raspagem Playwright Desktop
│   ├── browser.py                # Contexto Chrome Desktop com injeção de cookies
│   ├── profile.py                # Extração de bio, status privado e estado do botão
│   ├── actions.py                # Envio de follow e auto-cancelamento (unrequest)
│   └── extractor.py              # Download de Bio, Avatar HD, Destaques, Stories e Feed
│
├── flows/                        # Lógica de negócio de cada opção do menu
│   ├── follow.py                 # [1] Abordagem individual e em massa (alvos.txt)
│   ├── monitor.py                # [2] Checagem, cascata de recusa, vácuo e download
│   ├── direct.py                 # [3] Download direto de perfis públicos ou aceitos
│   ├── history.py                # [4] Visualização tabular de histórico e status
│   ├── pool_menu.py              # [5] Submenu de gerenciamento e testes do pool
│   └── sentinel.py               # [6] Modo Sentinela (Loop contínuo 24/7)
│
├── main.py                       # CLI enxuto com menu interativo
├── alvos.txt                     # Arquivo de entrada para lista de alvos em lote
├── MANUAL_DO_CLIENTE.md          # Manual de instruções passo a passo para o cliente
├── requirements.txt              # Dependências do projeto
└── .env.example                  # Template de configuração de credenciais
```

---

## 🚀 Instalação e Inicialização Rápida

1. **Instale as dependências:**

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure o ambiente:**
   Copie o template `.env.example` para `.env` ou utilize a opção `[5]` no menu do programa para adicionar suas contas:

   ```bash
   cp .env.example .env
   ```

3. **Inicie o sistema:**
   ```bash
   python main.py
   ```

---

## 📖 Documentação Detalhada

Para instruções passo a passo de como capturar o `sessionid`, cadastrar contas bots, importar alvos em lote e operar o sistema, consulte o [Manual de Uso do Cliente (MANUAL_DO_CLIENTE.md)](MANUAL_DO_CLIENTE.md).
