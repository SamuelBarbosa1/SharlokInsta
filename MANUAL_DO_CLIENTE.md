# 🕵️‍♂️ SharlokInsta - Manual de Uso do Cliente

Guia prático e passo a passo para configuração, operação e extração de perfis do Instagram através do **SharlokInsta**.

---

## 📌 Sumário

1. [Visão Geral](#-visão-geral)
2. [Pré-requisitos](#-pré-requisitos)
3. [Instalação e Configuração](#-instalação-e-configuração)
4. [Como Obter o SessionID do Instagram](#-como-obter-o-sessionid-do-instagram)
5. [Menu Principal e Funcionalidades](#-menu-principal-e-funcionalidades)
6. [Importação em Massa de Alvos (`alvos.txt`)](#-importação-em-massa-de-alvos-alvostxt)
7. [Modo Sentinela 24/7 (Automação Completa)](#-modo-sentinela-247-automação-completa)
8. [Onde Encontrar os Arquivos Extraídos](#-onde-encontrar-os-arquivos-extraídos)
9. [Solução de Dúvidas Frequentes (FAQ)](#-solução-de-dúvidas-frequentes-faq)

---

## 🔍 Visão Geral

O **SharlokInsta** é uma ferramenta desktop desenvolvida para análise, extração OSINT e monitoramento de perfis do Instagram. Ele simula navegação humana legítima pelo Google Chrome Desktop (Windows), contornando limitações mobile.

### O que o sistema é capaz de fazer:

- 📸 **Download de Feed:** Baixa todas as fotos na resolução máxima (1080x1080).
- 🌟 **Download de Destaques (Highlights):** Mapeia todas as pastas e baixa fotos e vídeos (`.mp4`).
- ⏱️ **Download de Stories (24h):** Captura stories ativos vigentes.
- 📝 **Relatório Completo:** Exporta foto de avatar em HD, contadores (posts, seguidores, seguindo), bio completa com emojis e links externos em `bio.txt` e `dados_perfil.json`.
- 👥 **Pool de Múltiplas Contas Fantoches:** Gerencia de 1 a dezenas de contas com rotação automática.
- 🔄 **Cascata Inteligente de Recusa & Vácuo:** Se uma conta for rejeitada ou deixada no vácuo, o robô automaticamente cancela a solicitação pendente e passa a vez para outro bot de forma aleatória.

---

## 💻 Pré-requisitos

- **Sistema Operacional:** Windows 10/11, Linux ou macOS.
- **Python:** Versão 3.10 ou superior ([Download Python](https://www.python.org/downloads/)).
  > _Ao instalar no Windows, marque a caixinha **"Add Python to PATH"**._
- **Navegador Google Chrome** instalado.

---

## 🚀 Instalação e Configuração

### 1. Clonar ou Extrair o Projeto

Abra o terminal (PowerShell ou CMD) na pasta do projeto:

```powershell
cd c:\caminho\para\SharlokInsta
```

### 2. Instalar as Dependências

Execute o comando abaixo para instalar as bibliotecas necessárias:

```powershell
pip install -r requirements.txt
playwright install chromium
```

---

## 🔑 Como Obter o SessionID do Instagram

O sistema não pede senhas: ele utiliza cookies de sessão já autenticados no navegador, sendo muito mais seguro contra bloqueios.

### Passo a passo no Chrome Desktop:

1. Abra o Google Chrome no seu computador e faça login na sua conta do Instagram.
2. Instale a extensão gratuita **Cookie-Editor** (disponível na Chrome Web Store).
3. Estando na página inicial do Instagram (`instagram.com`), clique no ícone da extensão **Cookie-Editor**.
4. Procure pelos seguintes cookies:
   - **`sessionid`**: Clique nele e copie o valor completo (uma string longa contendo números e letras).
   - **`ds_user_id`**: É o seu ID numérico no Instagram (aparece também no início do sessionid).
5. Você pode cadastrar esse `sessionid` de duas formas:
   - **Pelo menu do programa:** Abrindo o sistema e escolhendo a opção `[5] 👥 Gerenciar Pool de Contas` $\rightarrow$ `[1] Adicionar Nova Conta Fantoche`.
   - **Pelo arquivo `.env`:** Criando/editando o arquivo `.env` na raiz do projeto:
     ```env
     IG_USER=seu_usuario
     IG_DS_USER_ID=seu_ds_user_id
     IG_SESSIONID=seu_sessionid_aqui
     ```

---

## 🧭 Menu Principal e Funcionalidades

Ao executar:

```powershell
python main.py
```

Você verá a interface interativa:

```text
╔══════════════════════════════════════════════════════════╗
║       🕵️‍♂️ SHARLOK INSTA - DESKTOP AUTOMATION (PC)         ║
║       Multi-Contas, Cascata & Monitoramento Sentinela    ║
╚══════════════════════════════════════════════════════════╝
 [1] 🎯 Enviar Solicitação para Alvos (Individual ou Em Massa)
 [2] 🔄 Verificar Solicitações & Cascata de Rejeição
 [3] ⚡ Baixar Perfil Agora (Alvos Já Aceitos ou Públicos)
 [4] 📋 Ver Histórico de Alvos e Status da Cascata
 [5] 👥 Gerenciar Pool de Contas (Adicionar Conta 2, Listar)
 [6] 👁️ Iniciar Modo Sentinela (Loop Automático 24/7)
 [0] 🚪 Sair
```

### Detalhes de Cada Opção:

#### `[1] 🎯 Enviar Solicitação para Alvos`

Permite abordar alvos privados:

- **`[1] 👤 Abordar 1 Alvo Manualmente:`** Você digita o @ do alvo, escolhe qual conta fantoche utilizará e o robô envia a solicitação pelo Chrome Desktop.
- **`[2] 📂 Carregar Lista de Alvos em Massa (alvos.txt):`** O robô lê uma lista de alvos e distribui proporcionalmente entre as contas ativas do pool.

#### `[2] 🔄 Verificar Solicitações & Cascata de Rejeição`

Faz uma varredura única em todos os alvos cadastrados:

- Se foi aceito: dispara imediatamente o download de tudo (Feed, Destaques, Stories, Bio).
- Se foi recusado: ativa o cooldown e prepara a próxima conta fantoche.
- Se está em vácuo (sem resposta pelo tempo limite): cancela a solicitação e passa a vez para outro bot.

#### `[3] ⚡ Baixar Perfil Agora`

Extrai o conteúdo de qualquer perfil público ou privado que a sua conta já siga. Permite definir a quantidade de rolagens no feed (padrão 6 rolagens, ~70 fotos).

#### `[4] 📋 Ver Histórico de Alvos e Status da Cascata`

Mostra uma tabela organizada com:

- Nome do alvo
- Status atual (`AGUARDANDO_APROVACAO`, `REJEITADO_COOLDOWN`, `CONCLUIDO`, etc.)
- Conta responsável atual
- Tempo de espera ou quantidade de mídias salvas.

#### `[5] 👥 Gerenciar Pool de Contas`

Permite gerenciar seu exército de contas bots:

- Adicionar novas contas informando `@` e `sessionid`.
- Ativar ou desativar contas temporariamente.
- Atualizar `sessionid` de contas cuja sessão tenha expirado.
- **Testar Login de Todas as Contas:** O robô abre o navegador em segundo plano e confirma em tempo real se a sessão de cada conta está ativa ou desconectada.

#### `[6] 👁️ Iniciar Modo Sentinela (Loop Automático 24/7)`

O modo mais poderoso da ferramenta. Deixa o sistema rodando continuamente em segundo plano (você define o intervalo, ex: a cada 30 minutos). O robô verifica aceites, cancela vácuos, faz rotações de bots e baixa conteúdos sozinho!

> _Para pausar o Modo Sentinela e voltar ao menu, pressione `Ctrl + C` no terminal._

---

## 📂 Importação em Massa de Alvos (`alvos.txt`)

Em vez de adicionar alvos um por um, utilize o arquivo `alvos.txt` na raiz da pasta:

1. Abra o arquivo `alvos.txt` em qualquer editor de texto.
2. Digite um username por linha (com ou sem `@`):
   ```text
   alvo_um
   alvo_dois
   @alvo_tres
   ```
3. Abra o programa e escolha a opção `[1]` $\rightarrow$ `[2] Carregar Lista de Alvos em Massa`.
4. O sistema exibirá a tabela de distribuição uniforme entre suas contas ativas (round-robin) e pedirá confirmação antes do envio.
5. As requisições são enviadas com intervalo humanizado (5 a 10 segundos) para proteção anti-bloqueio.

---

## 👁️ Modo Sentinela 24/7 (Automação Completa)

Ao ativar a opção `[6]`:

1. O sistema pergunta o intervalo desejado (ex: `30` minutos).
2. Ele executa a checagem de todos os alvos.
3. Se algum alvo aceitou $\rightarrow$ Baixa todo o perfil imediatamente.
4. Se algum alvo recusou $\rightarrow$ Agenda a próxima conta para tentar após o cooldown.
5. Se algum alvo não respondeu após o tempo limite $\rightarrow$ Desfaz a solicitação e manda outro bot.
6. Dorme e aguarda o próximo ciclo sem gastar memória ou CPU desnecessária.

---

## 📁 Onde Encontrar os Arquivos Extraídos

Todos os downloads são salvos de forma organizada na pasta `downloads/`:

```text
downloads/
└── @nome_do_alvo/
    ├── avatar_perfil.jpg          # Foto de perfil em resolução original
    ├── bio.txt                    # Relatório de texto com biografia, seguidores e links
    ├── dados_perfil.json          # Metadados completos estruturados em JSON
    ├── foto_1.jpg                 # Fotos do feed em alta definição (1080x1080)
    ├── foto_2.jpg
    ├── destaques/                 # Pasta com todas as mídias de destaques (Highlights)
    │   ├── destaque_1_slide_1.jpg
    │   └── destaque_1_slide_2.mp4
    └── stories/                   # Pasta com Stories ativos das últimas 24 horas
        ├── story_1.jpg
        └── story_2.mp4
```

---

## ❓ Solução de Dúvidas Frequentes (FAQ)

### 1. O que acontece se a sessão expirar?

Se o Instagram deslogar uma conta fantoche, acesse a opção `[5]` $\rightarrow$ `[4] Testar Login de Todas as Contas`. Ela indicará qual conta está desconectada. Basta pegar o novo `sessionid` no navegador e atualizar na opção `[5]` $\rightarrow$ `[3]`.

### 2. Minhas senhas ou contas correm risco?

O sistema não armazena senhas em texto puro nem as envia para nenhum servidor externo. Todo o tráfego ocorre localmente entre o seu computador e os servidores oficiais do Instagram.

### 3. Como ajustar o tempo de cooldown ou limite de vácuo?

No arquivo `core/config.py`:

- `COOLDOWN_MINUTOS = 120`: Tempo de espera após uma recusa (padrão 2 horas).
- `TIMEOUT_VACUO_MINUTOS = 2880`: Tempo máximo aguardando resposta (padrão 48 horas / 2 dias).

---

_SharlokInsta Desktop - Desenvolvido para máxima discrição e eficiência OSINT._
