package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"sharlok-engine/client"
	"sharlok-engine/downloader"
)

type OutputSummary struct {
	Sucesso          bool     `json:"sucesso"`
	Username         string   `json:"username"`
	UserID           string   `json:"user_id"`
	TotalSeguidores  int      `json:"total_seguidores"`
	TotalSeguindo    int      `json:"total_seguindo"`
	TotalMutuos      int      `json:"total_mutuos"`
	TotalMidiasFeed  int      `json:"total_midias_feed"`
	TotalArquivos    int      `json:"total_arquivos"`
	PastaDestino     string   `json:"pasta_destino"`
	TempoDecorridoS  float64  `json:"tempo_decorrido_s"`
	StatusSeguidores string   `json:"status_seguidores"`
	StatusSeguindo   string   `json:"status_seguindo"`
	Erro             string   `json:"erro,omitempty"`
}

func main() {
	usernameFlag := flag.String("username", "", "Username do perfil alvo (sem @)")
	sessionIDFlag := flag.String("sessionid", "", "Cookie sessionid do Instagram autenticado")
	dsUserIDFlag := flag.String("ds_user_id", "", "ID numérico do usuário autenticado (opcional)")
	outDirFlag := flag.String("out", "", "Pasta de destino para mídias e relatórios")
	maxFollowersFlag := flag.Int("max_followers", 0, "Limite de seguidores a paginar (0 = todos)")
	maxFollowingFlag := flag.Int("max_following", 0, "Limite de seguindo a paginar (0 = todos)")
	maxFeedFlag := flag.Int("max_feed", 120, "Limite de fotos do feed a baixar")
	workersFlag := flag.Int("workers", 12, "Número de Goroutines simultâneas para download")
	delayMsFlag := flag.Int("delay_ms", 350, "Delay em milissegundos entre páginas REST de seguidores/seguindo")
	jsonOutputFlag := flag.Bool("json", false, "Exibe apenas o JSON final no stdout")

	flag.Parse()

	cleanUser := strings.TrimPrefix(strings.TrimSpace(*usernameFlag), "@")
	if cleanUser == "" || *sessionIDFlag == "" {
		fmt.Fprintf(os.Stderr, "Uso obrigatório: -username <alvo> -sessionid <cookie>\n")
		os.Exit(1)
	}

	inicio := time.Now()
	pastaDestino := *outDirFlag
	if pastaDestino == "" {
		pastaDestino = filepath.Join("downloads", "@"+cleanUser)
	}
	_ = os.MkdirAll(pastaDestino, 0755)

	logPrint := func(format string, a ...interface{}) {
		if !*jsonOutputFlag {
			fmt.Printf(format+"\n", a...)
		}
	}

	logPrint("============================================================")
	logPrint("[*] SHARLOK ENGINE (GOLANG TURBO REST) INICIADO")
	logPrint("[*] Alvo: @%s | Workers: %d | Delay REST: %dms", cleanUser, *workersFlag, *delayMsFlag)
	logPrint("============================================================")

	igClient := client.NewInstagramClient(*sessionIDFlag, *dsUserIDFlag)

	// [1/5] Perfil e Biografia via REST
	logPrint("\n[1/5] Extraindo Dados e Biografia via REST Web Profile...")
	perfilRes, err := igClient.ObterPerfil(cleanUser)
	if err != nil {
		emitirErro(*jsonOutputFlag, cleanUser, fmt.Sprintf("Erro ao obter perfil: %v", err))
		os.Exit(2)
	}

	u := perfilRes.Data.User
	userID := u.ID
	postsCountStr := fmt.Sprintf("%d posts", u.EdgeOwnerToTimelineMedia.Count)
	seguidoresCountStr := fmt.Sprintf("%d seguidores", u.EdgeFollowedBy.Count)
	seguindoCountStr := fmt.Sprintf("%d seguindo", u.EdgeFollow.Count)

	logPrint("  [+] Perfil identificado: %s (ID: %s)", u.FullName, userID)
	logPrint("  [+] Métricas: %s | %s | %s", postsCountStr, seguidoresCountStr, seguindoCountStr)

	isPrivadoNaoSeguido := u.IsPrivate && !u.FollowedByViewer
	if isPrivadoNaoSeguido {
		logPrint("\n[!] ALERTA OSINT: O perfil @%s é PRIVADO e a conta fantoche atual NÃO é seguidora aprovada.", cleanUser)
		logPrint("    - Avatar HD e Biografia pública foram extraídos com sucesso.")
		logPrint("    - Posts, mídias e conexões completas são bloqueados pela Meta até aprovação do pedido.")
		logPrint("    - Dica: Envie solicitação de seguir via 'Alvos & Monitoramento' com o 'Sentinela 24/7' ativo.")
	}

	// Salva bio.txt
	bioTxtPath := filepath.Join(pastaDestino, "bio.txt")
	bioContent := fmt.Sprintf("============================================================\n"+
		" PERFIL DO INSTAGRAM: @%s\n"+
		" Nome: %s (ID Numérico: %s)\n"+
		" %s | %s | %s\n"+
		"============================================================\n\n"+
		"--- BIOGRAFIA E INFORMAÇÕES ---\n%s\n\n",
		cleanUser, u.FullName, userID, postsCountStr, seguidoresCountStr, seguindoCountStr, u.Biography)
	if u.ExternalURL != "" {
		bioContent += fmt.Sprintf("--- LINK EXTERNO NA BIO ---\n%s\n\n", u.ExternalURL)
	}
	bioContent += "============================================================\n"
	_ = os.WriteFile(bioTxtPath, []byte(bioContent), 0644)
	logPrint("  [>] Arquivo bio.txt gerado com sucesso!")

	// Fila de downloads para o Pool de Goroutines
	var downloadsQueue []downloader.DownloadItem

	if u.ProfilePicURLHD != "" {
		downloadsQueue = append(downloadsQueue, downloader.DownloadItem{
			URL:      u.ProfilePicURLHD,
			DestPath: filepath.Join(pastaDestino, "avatar_perfil.jpg"),
			Label:    "Avatar HD",
			IsVideo:  false,
		})
	} else if u.ProfilePicURL != "" {
		downloadsQueue = append(downloadsQueue, downloader.DownloadItem{
			URL:      u.ProfilePicURL,
			DestPath: filepath.Join(pastaDestino, "avatar_perfil.jpg"),
			Label:    "Avatar",
			IsVideo:  false,
		})
	}

	// [2/5] Mapeamento de Feed
	logPrint("\n[2/5] Mapeando mídias do Feed...")
	feedEdges := u.EdgeOwnerToTimelineMedia.Edges
	fotoIdx := 0
	for _, edge := range feedEdges {
		if *maxFeedFlag > 0 && fotoIdx >= *maxFeedFlag {
			break
		}
		node := edge.Node

		// Se for carrossel com múltiplos filhos
		if len(node.EdgeSidecarToChildren.Edges) > 0 {
			for _, child := range node.EdgeSidecarToChildren.Edges {
				if *maxFeedFlag > 0 && fotoIdx >= *maxFeedFlag {
					break
				}
				fotoIdx++
				cNode := child.Node
				targetURL := cNode.DisplayURL
				ext := "jpg"
				isVideo := cNode.IsVideo
				if isVideo && cNode.VideoURL != "" {
					targetURL = cNode.VideoURL
					ext = "mp4"
				}
				if targetURL != "" {
					downloadsQueue = append(downloadsQueue, downloader.DownloadItem{
						URL:      targetURL,
						DestPath: filepath.Join(pastaDestino, fmt.Sprintf("foto_%d.%s", fotoIdx, ext)),
						Label:    fmt.Sprintf("Feed #%d", fotoIdx),
						IsVideo:  isVideo,
					})
				}
			}
		} else {
			fotoIdx++
			targetURL := node.DisplayURL
			ext := "jpg"
			isVideo := node.IsVideo
			if isVideo && node.VideoURL != "" {
				targetURL = node.VideoURL
				ext = "mp4"
			}
			if targetURL != "" {
				downloadsQueue = append(downloadsQueue, downloader.DownloadItem{
					URL:      targetURL,
					DestPath: filepath.Join(pastaDestino, fmt.Sprintf("foto_%d.%s", fotoIdx, ext)),
					Label:    fmt.Sprintf("Feed #%d", fotoIdx),
					IsVideo:  isVideo,
				})
			}
		}
	}
	logPrint("  [+] %d mídia(s) do feed enfileiradas para download concorrente.", len(downloadsQueue)-1)

	// [3/5] Paginação REST de Seguidores
	var listaSeguidores []string
	stSeguidores := "PRIVADO_BLOQUEADO"
	if isPrivadoNaoSeguido {
		logPrint("\n[3/5] Seguidores: Alvo privado sem permissão de seguidor. Pulando requisição REST para evitar bloqueio.")
	} else {
		logPrint("\n[3/5] Paginando SEGUIDORES via API REST (/friendships/%s/followers)...", userID)
		delay := time.Duration(*delayMsFlag) * time.Millisecond
		progressoSeguidores := func(tipo string, pagina, coletados, totalEsperado int) {
			logPrint("    [*] Paginação %s | Página %d: %d contas acumuladas...", tipo, pagina, coletados)
		}

		var errSeguidores error
		listaSeguidores, stSeguidores, errSeguidores = igClient.PaginacaoSeguidores(userID, *maxFollowersFlag, delay, progressoSeguidores)
		if errSeguidores != nil {
			logPrint("  [-] Aviso seguidores: %v (Status: %s)", errSeguidores, stSeguidores)
		} else {
			logPrint("  [+] TOTAL DE SEGUIDORES COLETADOS: %d contas!", len(listaSeguidores))
		}
	}

	// [4/5] Paginação REST de Seguindo
	var listaSeguindo []string
	stSeguindo := "PRIVADO_BLOQUEADO"
	if isPrivadoNaoSeguido {
		logPrint("\n[4/5] Seguindo: Alvo privado sem permissão de seguidor. Pulando requisição REST para evitar bloqueio.")
	} else {
		logPrint("\n[4/5] Paginando SEGUINDO via API REST (/friendships/%s/following)...", userID)
		delay := time.Duration(*delayMsFlag) * time.Millisecond
		progressoSeguindo := func(tipo string, pagina, coletados, totalEsperado int) {
			logPrint("    [*] Paginação %s | Página %d: %d contas acumuladas...", tipo, pagina, coletados)
		}

		var errSeguindo error
		listaSeguindo, stSeguindo, errSeguindo = igClient.PaginacaoSeguindo(userID, *maxFollowingFlag, delay, progressoSeguindo)
		if errSeguindo != nil {
			logPrint("  [-] Aviso seguindo: %v (Status: %s)", errSeguindo, stSeguindo)
		} else {
			logPrint("  [+] TOTAL DE SEGUINDO COLETADOS: %d contas!", len(listaSeguindo))
		}
	}

	// [5/5] Cruzamento de Conexões e Download Concorrente
	logPrint("\n[5/5] Cruzando Conexões e Disparando Worker Pool com %d Goroutines...", *workersFlag)

	mapSeguindo := make(map[string]bool)
	for _, s := range listaSeguindo {
		mapSeguindo[s] = true
	}
	mapSeguidores := make(map[string]bool)
	for _, s := range listaSeguidores {
		mapSeguidores[s] = true
	}

	var mutuos []string
	var apenasSeguidores []string
	var alvoSegueNaoSeguem []string

	for _, s := range listaSeguidores {
		if mapSeguindo[s] {
			mutuos = append(mutuos, s)
		} else {
			apenasSeguidores = append(apenasSeguidores, s)
		}
	}
	for _, s := range listaSeguindo {
		if !mapSeguidores[s] {
			alvoSegueNaoSeguem = append(alvoSegueNaoSeguem, s)
		}
	}

	sort.Strings(mutuos)
	sort.Strings(apenasSeguidores)
	sort.Strings(alvoSegueNaoSeguem)

	// Salva seguidores.txt
	_ = salvarListaTxt(filepath.Join(pastaDestino, "seguidores.txt"), fmt.Sprintf("=== SEGUIDORES DE @%s ===\nTotal: %d\n\n", cleanUser, len(listaSeguidores)), listaSeguidores)
	// Salva seguindo.txt
	_ = salvarListaTxt(filepath.Join(pastaDestino, "seguindo.txt"), fmt.Sprintf("=== CONTAS QUE @%s SEGUE ===\nTotal: %d\n\n", cleanUser, len(listaSeguindo)), listaSeguindo)
	// Salva conexoes_mutuas.txt
	_ = salvarListaTxt(filepath.Join(pastaDestino, "conexoes_mutuas.txt"), fmt.Sprintf("=== CONEXÕES MÚTUAS DE @%s (SEGUE E É SEGUIDO) ===\nTotal: %d\n\n", cleanUser, len(mutuos)), mutuos)

	logPrint("  [+] Conexões Mútuas: %d contas em comum", len(mutuos))
	logPrint("  [>] Iniciando download paralelo de %d arquivo(s) de mídia...", len(downloadsQueue))

	pool := downloader.NewDownloaderPool(*workersFlag)
	onDlProg := func(concluidos, total int, item downloader.DownloadItem, err error) {
		if err != nil {
			logPrint("    [-] Falha ao baixar %s: %v", item.Label, err)
		} else {
			logPrint("    [>] Baixado (%d/%d): %s", concluidos, total, filepath.Base(item.DestPath))
		}
	}
	dlResults := pool.DownloadAll(downloadsQueue, onDlProg)

	arquivosBaixadosComSucesso := 0
	for _, res := range dlResults {
		if res.Error == nil {
			arquivosBaixadosComSucesso++
		}
	}

	// Monta dados_perfil.json
	dadosJSON := map[string]interface{}{
		"username":     cleanUser,
		"avatar_salvo": u.ProfilePicURLHD != "" || u.ProfilePicURL != "",
		"contadores": map[string]string{
			"posts":      postsCountStr,
			"seguidores": seguidoresCountStr,
			"seguindo":   seguindoCountStr,
		},
		"links_bio": []map[string]string{
			{"texto": "Link Externo", "url": u.ExternalURL},
		},
		"conexoes": map[string]interface{}{
			"seguidores": map[string]interface{}{
				"status":               stSeguidores,
				"motivo":               "OK",
				"bloqueado_ou_privado": stSeguidores == "RESTRITO" || stSeguidores == "BLOQUEADO",
				"total_extraido":       len(listaSeguidores),
				"contas":               listaSeguidores,
			},
			"seguindo": map[string]interface{}{
				"status":               stSeguindo,
				"motivo":               "OK",
				"bloqueado_ou_privado": stSeguindo == "RESTRITO" || stSeguindo == "BLOQUEADO",
				"total_extraido":       len(listaSeguindo),
				"contas":               listaSeguindo,
			},
			"resumo_relacionamento": map[string]interface{}{
				"seguem_de_volta_mutuo":             mutuos,
				"total_mutuo":                       len(mutuos),
				"apenas_seguidores":                 apenasSeguidores,
				"alvo_segue_mas_nao_seguem_de_volta": alvoSegueNaoSeguem,
			},
		},
		"total_destaques_baixados": 0,
		"destaques_arquivos":       []string{},
		"total_stories_baixados":   0,
		"stories_arquivos":         []string{},
		"total_fotos_feed":         arquivosBaixadosComSucesso,
		"engine_utilizada":         "GOLANG_TURBO_REST",
	}

	jsonBytes, _ := json.MarshalIndent(dadosJSON, "", "    ")
	_ = os.WriteFile(filepath.Join(pastaDestino, "dados_perfil.json"), jsonBytes, 0644)

	duracao := time.Since(inicio).Seconds()

	logPrint("\n============================================================")
	logPrint("[✔] EXTRAÇÃO FINALIZADA COM SUCESSO EM %.2f SEGUNDOS!", duracao)
	logPrint("  - Seguidores capturados: %d contas", len(listaSeguidores))
	logPrint("  - Seguindo capturados  : %d contas", len(listaSeguindo))
	logPrint("  - Conexões mútuas      : %d contas", len(mutuos))
	logPrint("  - Mídias baixadas      : %d arquivos", arquivosBaixadosComSucesso)
	logPrint("  - Pasta de destino     : %s", pastaDestino)
	logPrint("============================================================")

	if *jsonOutputFlag {
		resumo := OutputSummary{
			Sucesso:          true,
			Username:         cleanUser,
			UserID:           userID,
			TotalSeguidores:  len(listaSeguidores),
			TotalSeguindo:    len(listaSeguindo),
			TotalMutuos:      len(mutuos),
			TotalMidiasFeed:  arquivosBaixadosComSucesso,
			TotalArquivos:    arquivosBaixadosComSucesso,
			PastaDestino:     pastaDestino,
			TempoDecorridoS:  duracao,
			StatusSeguidores: stSeguidores,
			StatusSeguindo:   stSeguindo,
		}
		resJSON, _ := json.Marshal(resumo)
		fmt.Println(string(resJSON))
	}
}

func salvarListaTxt(caminho, cabecalho string, lista []string) error {
	var sb strings.Builder
	sb.WriteString(cabecalho)
	for _, u := range lista {
		sb.WriteString("@" + u + "\n")
	}
	return os.WriteFile(caminho, []byte(sb.String()), 0644)
}

func emitirErro(jsonOutput bool, username, mensagem string) {
	if jsonOutput {
		res := OutputSummary{
			Sucesso:  false,
			Username: username,
			Erro:     mensagem,
		}
		b, _ := json.Marshal(res)
		fmt.Println(string(b))
	} else {
		fmt.Fprintf(os.Stderr, "[-] ERRO: %s\n", mensagem)
	}
}

