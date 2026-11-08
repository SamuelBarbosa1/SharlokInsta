package client

import (
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	IGAppID   = "936619743392459"
	DefaultUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
	BaseURL   = "https://www.instagram.com"
)

var (
	ErrPerfilNaoEncontrado = errors.New("perfil não encontrado no Instagram")
	ErrSessaoExpirada      = errors.New("sessão expirada ou challenge exigido pela Meta")
)

type InstagramClient struct {
	SessionID string
	DSUserID  string
	HTTP      *http.Client
	UserAgent string
}

func NewInstagramClient(sessionID, dsUserID string) *InstagramClient {
	if dsUserID == "" && strings.Contains(sessionID, "%3A") {
		parts := strings.Split(sessionID, "%3A")
		if len(parts) > 0 {
			dsUserID = parts[0]
		}
	} else if dsUserID == "" && strings.Contains(sessionID, ":") {
		parts := strings.Split(sessionID, ":")
		if len(parts) > 0 {
			dsUserID = parts[0]
		}
	}

	return &InstagramClient{
		SessionID: sessionID,
		DSUserID:  dsUserID,
		UserAgent: DefaultUA,
		HTTP: &http.Client{
			Timeout: 25 * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				dest := strings.ToLower(req.URL.String())
				if strings.Contains(dest, "/accounts/login") || strings.Contains(dest, "/challenge/") {
					return ErrSessaoExpirada
				}
				if len(via) >= 5 {
					return errors.New("muitos redirecionamentos HTTP")
				}
				return nil
			},
		},
	}
}

func (c *InstagramClient) applyHeaders(req *http.Request, referer string) {
	req.Header.Set("User-Agent", c.UserAgent)
	req.Header.Set("X-IG-App-ID", IGAppID)
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("X-ASBD-ID", "129477")
	req.Header.Set("X-IG-WWW-Claim", "0")
	req.Header.Set("Sec-Ch-Ua", "\"Chromium\";v=\"128\", \"Not;A=Brand\";v=\"24\", \"Google Chrome\";v=\"128\"")
	req.Header.Set("Sec-Ch-Ua-Mobile", "?0")
	req.Header.Set("Sec-Ch-Ua-Platform", "\"Windows\"")
	req.Header.Set("Sec-Fetch-Site", "same-origin")
	req.Header.Set("Sec-Fetch-Mode", "cors")
	req.Header.Set("Sec-Fetch-Dest", "empty")
	req.Header.Set("Accept", "*/*")
	req.Header.Set("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
	if referer != "" {
		req.Header.Set("Referer", referer)
	}

	cleanSession := strings.TrimSpace(c.SessionID)
	cleanSession = strings.Trim(cleanSession, "\"'; ")
	cleanSession = strings.ReplaceAll(cleanSession, "%253A", "%3A")
	cleanSession = strings.ReplaceAll(cleanSession, "%253a", "%3A")

	cookieStr := fmt.Sprintf("sessionid=%s;", cleanSession)
	if c.DSUserID != "" {
		cookieStr += fmt.Sprintf(" ds_user_id=%s;", c.DSUserID)
	}
	req.Header.Set("Cookie", cookieStr)
}

func (c *InstagramClient) ObterPerfil(username string) (*WebProfileInfoResponse, error) {
	clean := strings.TrimPrefix(strings.TrimSpace(username), "@")
	reqURL := fmt.Sprintf("%s/api/v1/users/web_profile_info/?username=%s", BaseURL, url.QueryEscape(clean))

	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, err
	}
	c.applyHeaders(req, fmt.Sprintf("%s/%s/", BaseURL, clean))

	resp, err := c.HTTP.Do(req)
	if err != nil {
		if errors.Is(err, ErrSessaoExpirada) {
			return nil, fmt.Errorf("%w: atualize o SessionID da conta no Pool", ErrSessaoExpirada)
		}
		return nil, fmt.Errorf("falha na requisição de perfil: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("erro lendo corpo da resposta: %w", err)
	}

	bodyLower := strings.ToLower(string(bodyBytes))
	if resp.StatusCode == 401 || (resp.StatusCode == 403 && (strings.Contains(bodyLower, "login_required") || strings.Contains(bodyLower, "challenge_required"))) {
		return nil, fmt.Errorf("%w (HTTP %d)", ErrSessaoExpirada, resp.StatusCode)
	}

	if resp.StatusCode == 200 {
		var res WebProfileInfoResponse
		if err := json.Unmarshal(bodyBytes, &res); err == nil && res.Data.User.Username != "" {
			return &res, nil
		}
	}

	// Fallback 1: API /api/v1/users/search/ + /friendships/show/
	fbRes, fbErr := c.obterPerfilFallbackSearch(clean)
	if fbErr == nil && fbRes != nil {
		return fbRes, nil
	}
	if errors.Is(fbErr, ErrSessaoExpirada) {
		return nil, fbErr
	}

	// Fallback 2: Extração direta via Documento HTML do Perfil + /friendships/show/
	// Funciona mesmo quando web_profile_info (429/404) e search (400) estão sob rate-limit!
	htmlRes, htmlErr := c.obterPerfilFallbackHTML(clean)
	if htmlErr == nil && htmlRes != nil {
		return htmlRes, nil
	}
	if errors.Is(htmlErr, ErrPerfilNaoEncontrado) || errors.Is(htmlErr, ErrSessaoExpirada) {
		return nil, htmlErr
	}

	if resp.StatusCode == 429 {
		return nil, fmt.Errorf("rate limit temporário da Meta (HTTP 429) no endpoint REST (%v)", htmlErr)
	}
	if resp.StatusCode == 404 {
		return nil, fmt.Errorf("endpoint web_profile_info retornou 404 e fallbacks indisponíveis (%v)", htmlErr)
	}
	return nil, fmt.Errorf("resposta HTTP %d inesperada da Meta ao consultar perfil (%v)", resp.StatusCode, htmlErr)
}

func parseInstagramCompactCount(raw string) int {
	s := strings.TrimSpace(strings.ToLower(raw))
	s = strings.ReplaceAll(s, "\u00a0", "")
	s = strings.ReplaceAll(s, " ", "")
	if s == "" {
		return 0
	}
	mult := 1.0
	if strings.HasSuffix(s, "mil") {
		mult = 1000.0
		s = strings.TrimSuffix(s, "mil")
	} else if strings.HasSuffix(s, "k") {
		mult = 1000.0
		s = strings.TrimSuffix(s, "k")
	} else if strings.HasSuffix(s, "mi") || strings.HasSuffix(s, "m") {
		mult = 1000000.0
		s = strings.TrimSuffix(s, "mi")
		s = strings.TrimSuffix(s, "m")
	}
	s = strings.TrimSpace(s)
	if mult > 1.0 {
		s = strings.ReplaceAll(s, ",", ".")
		if val, err := strconv.ParseFloat(s, 64); err == nil {
			return int(val * mult)
		}
		return 0
	}
	s = strings.ReplaceAll(s, ".", "")
	s = strings.ReplaceAll(s, ",", "")
	if val, err := strconv.Atoi(s); err == nil {
		return val
	}
	return 0
}

func (c *InstagramClient) obterPerfilFallbackHTML(clean string) (*WebProfileInfoResponse, error) {
	pageURL := fmt.Sprintf("%s/%s/", BaseURL, url.PathEscape(clean))
	req, err := http.NewRequest("GET", pageURL, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("User-Agent", c.UserAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8")
	req.Header.Set("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
	req.Header.Set("Sec-Fetch-Site", "none")
	req.Header.Set("Sec-Fetch-Mode", "navigate")
	req.Header.Set("Sec-Fetch-Dest", "document")
	req.Header.Set("Upgrade-Insecure-Requests", "1")

	cleanSession := strings.TrimSpace(c.SessionID)
	cleanSession = strings.Trim(cleanSession, "\"'; ")
	cleanSession = strings.ReplaceAll(cleanSession, "%253A", "%3A")
	cleanSession = strings.ReplaceAll(cleanSession, "%253a", "%3A")
	cookieStr := fmt.Sprintf("sessionid=%s;", cleanSession)
	if c.DSUserID != "" {
		cookieStr += fmt.Sprintf(" ds_user_id=%s;", c.DSUserID)
	}
	req.Header.Set("Cookie", cookieStr)

	resp, err := c.HTTP.Do(req)
	if err != nil {
		if errors.Is(err, ErrSessaoExpirada) {
			return nil, ErrSessaoExpirada
		}
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 404 {
		return nil, fmt.Errorf("%w: @%s", ErrPerfilNaoEncontrado, clean)
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("HTML status %d", resp.StatusCode)
	}

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	htmlStr := string(bodyBytes)

	// Extrai o PK (ID numérico do perfil alvo) embutido no HTML do Instagram
	var foundPK string
	pkPatterns := []string{
		`"container_id":"(\d+)"`,
		`"profile_id":"(\d+)"`,
		`profilePage_(\d+)`,
		`"target_id":"(\d+)"`,
	}
	for _, pat := range pkPatterns {
		re := regexp.MustCompile(pat)
		if m := re.FindStringSubmatch(htmlStr); len(m) > 1 && m[1] != "" {
			foundPK = m[1]
			break
		}
	}

	// Verifica se a página realmente pertence a um perfil existente
	reOgTitle := regexp.MustCompile(`<meta[^>]+property="og:title"[^>]+content="([^"]+)"`)
	ogTitleMatch := reOgTitle.FindStringSubmatch(htmlStr)
	if foundPK == "" && len(ogTitleMatch) == 0 {
		return nil, fmt.Errorf("%w: @%s", ErrPerfilNaoEncontrado, clean)
	}

	fullName := clean
	if len(ogTitleMatch) > 1 {
		ogTitle := html.UnescapeString(ogTitleMatch[1])
		if idx := strings.Index(ogTitle, "(@"); idx > 0 {
			fullName = strings.TrimSpace(ogTitle[:idx])
		}
	}

	avatarURL := ""
	reOgImg := regexp.MustCompile(`<meta[^>]+property="og:image"[^>]+content="([^"]+)"`)
	if m := reOgImg.FindStringSubmatch(htmlStr); len(m) > 1 {
		avatarURL = html.UnescapeString(m[1])
	}

	var followersCount, followingCount, postsCount int
	var bioText string

	reDesc := regexp.MustCompile(`<meta[^>]+content="([^"]+)"[^>]+name="description"|<meta[^>]+name="description"[^>]+content="([^"]+)"|<meta[^>]+property="og:description"[^>]+content="([^"]+)"`)
	if m := reDesc.FindStringSubmatch(htmlStr); len(m) > 0 {
		rawDesc := ""
		for i := 1; i < len(m); i++ {
			if m[i] != "" {
				rawDesc = html.UnescapeString(m[i])
				break
			}
		}
		if rawDesc != "" {
			reFollowers := regexp.MustCompile(`(?i)([\d.,]+\s*(?:mil|mi|k|m)?)\s*(?:seguidores|followers)`)
			if mf := reFollowers.FindStringSubmatch(rawDesc); len(mf) > 1 {
				followersCount = parseInstagramCompactCount(mf[1])
			}
			reFollowing := regexp.MustCompile(`(?i)([\d.,]+\s*(?:mil|mi|k|m)?)\s*(?:seguindo|following|a\s+seguir)`)
			if mfg := reFollowing.FindStringSubmatch(rawDesc); len(mfg) > 1 {
				followingCount = parseInstagramCompactCount(mfg[1])
			} else {
				reFollowingAlt := regexp.MustCompile(`(?i)(?:seguindo|following|a\s+seguir)\s*([\d.,]+\s*(?:mil|mi|k|m)?)`)
				if mfg2 := reFollowingAlt.FindStringSubmatch(rawDesc); len(mfg2) > 1 {
					followingCount = parseInstagramCompactCount(mfg2[1])
				}
			}
			rePosts := regexp.MustCompile(`(?i)([\d.,]+\s*(?:mil|mi|k|m)?)\s*(?:posts?|publicaç[õo]es|publicacao)`)
			if mp := rePosts.FindStringSubmatch(rawDesc); len(mp) > 1 {
				postsCount = parseInstagramCompactCount(mp[1])
			}
			reBio := regexp.MustCompile(`(?s)(?:no Instagram|on Instagram):\s*"(.*)"\s*$`)
			if mb := reBio.FindStringSubmatch(rawDesc); len(mb) > 1 {
				bioText = strings.TrimSpace(mb[1])
			}
		}
	}

	isPrivate := strings.Contains(htmlStr, `"is_private":true`)
	followedByViewer := false
	requestedByViewer := false

	if foundPK != "" {
		fShowURL := fmt.Sprintf("%s/api/v1/friendships/show/%s/", BaseURL, foundPK)
		if reqF, errF := http.NewRequest("GET", fShowURL, nil); errF == nil {
			c.applyHeaders(reqF, fmt.Sprintf("%s/%s/", BaseURL, clean))
			if respF, errDo := c.HTTP.Do(reqF); errDo == nil {
				bF, _ := io.ReadAll(respF.Body)
				respF.Body.Close()
				if respF.StatusCode == 200 {
					var fShow FriendshipShowResponse
					if json.Unmarshal(bF, &fShow) == nil {
						followedByViewer = fShow.Following
						requestedByViewer = fShow.OutgoingRequest
						isPrivate = fShow.IsPrivate
					}
				}
			}
		}
	}

	var res WebProfileInfoResponse
	res.Status = "ok"
	res.Data.User.ID = foundPK
	res.Data.User.Username = clean
	res.Data.User.FullName = fullName
	res.Data.User.Biography = bioText
	res.Data.User.ProfilePicURL = avatarURL
	res.Data.User.ProfilePicURLHD = avatarURL
	res.Data.User.IsPrivate = isPrivate
	res.Data.User.FollowedByViewer = followedByViewer
	res.Data.User.RequestedByViewer = requestedByViewer
	res.Data.User.EdgeFollowedBy.Count = followersCount
	res.Data.User.EdgeFollow.Count = followingCount
	res.Data.User.EdgeOwnerToTimelineMedia.Count = postsCount

	return &res, nil
}

func (c *InstagramClient) obterPerfilFallbackSearch(clean string) (*WebProfileInfoResponse, error) {
	searchURL := fmt.Sprintf("%s/api/v1/users/search/?q=%s", BaseURL, url.QueryEscape(clean))
	req, err := http.NewRequest("GET", searchURL, nil)
	if err != nil {
		return nil, err
	}
	c.applyHeaders(req, fmt.Sprintf("%s/", BaseURL))

	resp, err := c.HTTP.Do(req)
	if err != nil {
		if errors.Is(err, ErrSessaoExpirada) {
			return nil, fmt.Errorf("%w: redirecionado para login", ErrSessaoExpirada)
		}
		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode == 401 {
		return nil, ErrSessaoExpirada
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("search HTTP %d", resp.StatusCode)
	}

	var searchRes UsersSearchResponse
	if err := json.Unmarshal(bodyBytes, &searchRes); err != nil {
		return nil, fmt.Errorf("search JSON inválido: %w", err)
	}

	var foundPK string
	var foundUsername, foundFullName, foundAvatar string
	var foundPrivate, foundVerified bool

	for _, u := range searchRes.Users {
		if strings.EqualFold(strings.TrimSpace(u.Username), clean) {
			foundUsername = u.Username
			foundFullName = u.FullName
			foundAvatar = u.ProfilePicURL
			foundPrivate = u.IsPrivate
			foundVerified = u.IsVerified
			if u.ID != "" {
				foundPK = u.ID
			} else if u.PK != nil {
				foundPK = fmt.Sprintf("%v", u.PK)
				if strings.Contains(foundPK, ".") {
					// Caso float64 em JSON genérico
					if f, ok := u.PK.(float64); ok {
						foundPK = fmt.Sprintf("%.0f", f)
					}
				}
			}
			break
		}
	}

	if foundUsername == "" || foundPK == "" {
		return nil, fmt.Errorf("%w: @%s", ErrPerfilNaoEncontrado, clean)
	}

	// Consulta status de amizade (se segue ou se solicitou)
	followedByViewer := false
	requestedByViewer := false
	fShowURL := fmt.Sprintf("%s/api/v1/friendships/show/%s/", BaseURL, foundPK)
	if reqF, errF := http.NewRequest("GET", fShowURL, nil); errF == nil {
		c.applyHeaders(reqF, fmt.Sprintf("%s/%s/", BaseURL, clean))
		if respF, errDo := c.HTTP.Do(reqF); errDo == nil {
			bF, _ := io.ReadAll(respF.Body)
			respF.Body.Close()
			if respF.StatusCode == 200 {
				var fShow FriendshipShowResponse
				if json.Unmarshal(bF, &fShow) == nil {
					followedByViewer = fShow.Following
					requestedByViewer = fShow.OutgoingRequest
					foundPrivate = fShow.IsPrivate
				}
			}
		}
	}

	var res WebProfileInfoResponse
	res.Status = "ok"
	res.Data.User.ID = foundPK
	res.Data.User.Username = foundUsername
	res.Data.User.FullName = foundFullName
	res.Data.User.ProfilePicURL = foundAvatar
	res.Data.User.ProfilePicURLHD = foundAvatar
	res.Data.User.IsPrivate = foundPrivate
	res.Data.User.IsVerified = foundVerified
	res.Data.User.FollowedByViewer = followedByViewer
	res.Data.User.RequestedByViewer = requestedByViewer

	// Tenta enriquecer contadores e bio via /api/v1/users/<pk>/info/
	uInfoURL := fmt.Sprintf("%s/api/v1/users/%s/info/", BaseURL, foundPK)
	if reqI, errI := http.NewRequest("GET", uInfoURL, nil); errI == nil {
		c.applyHeaders(reqI, fmt.Sprintf("%s/%s/", BaseURL, clean))
		if respI, errDo := c.HTTP.Do(reqI); errDo == nil {
			bI, _ := io.ReadAll(respI.Body)
			respI.Body.Close()
			if respI.StatusCode == 200 {
				var mInfo MobileUserInfoResponse
				if json.Unmarshal(bI, &mInfo) == nil && mInfo.User.Username != "" {
					res.Data.User.Biography = mInfo.User.Biography
					res.Data.User.ExternalURL = mInfo.User.ExternalURL
					res.Data.User.EdgeOwnerToTimelineMedia.Count = mInfo.User.MediaCount
					res.Data.User.EdgeFollowedBy.Count = mInfo.User.FollowerCount
					res.Data.User.EdgeFollow.Count = mInfo.User.FollowingCount
					if mInfo.User.HDProfilePicInfo.URL != "" {
						res.Data.User.ProfilePicURLHD = mInfo.User.HDProfilePicInfo.URL
					}
				}
			}
		}
	}

	// Se o perfil for público ou já seguido pelo bot, busca mídias do feed via /api/v1/feed/user/<pk>/
	if !foundPrivate || followedByViewer {
		c.carregarMidiasFeedFallback(foundPK, clean, &res)
	}

	return &res, nil
}

func (c *InstagramClient) carregarMidiasFeedFallback(userID, clean string, res *WebProfileInfoResponse) {
	nextMaxID := ""
	for pag := 0; pag < 3; pag++ {
		feedURL := fmt.Sprintf("%s/api/v1/feed/user/%s/?count=33", BaseURL, userID)
		if nextMaxID != "" {
			feedURL += "&max_id=" + url.QueryEscape(nextMaxID)
		}
		req, err := http.NewRequest("GET", feedURL, nil)
		if err != nil {
			break
		}
		c.applyHeaders(req, fmt.Sprintf("%s/%s/", BaseURL, clean))
		resp, err := c.HTTP.Do(req)
		if err != nil {
			break
		}
		b, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != 200 {
			break
		}
		var fRes UserFeedMobileResponse
		if json.Unmarshal(b, &fRes) != nil || len(fRes.Items) == 0 {
			break
		}

		for _, item := range fRes.Items {
			var edge struct {
				Node struct {
					ID                    string `json:"id"`
					Shortcode             string `json:"shortcode"`
					DisplayURL            string `json:"display_url"`
					IsVideo               bool   `json:"is_video"`
					VideoURL              string `json:"video_url"`
					EdgeSidecarToChildren struct {
						Edges []struct {
							Node struct {
								ID         string `json:"id"`
								DisplayURL string `json:"display_url"`
								IsVideo    bool   `json:"is_video"`
								VideoURL   string `json:"video_url"`
							} `json:"node"`
						} `json:"edges"`
					} `json:"edge_sidecar_to_children"`
				} `json:"node"`
			}
			edge.Node.ID = item.ID
			edge.Node.Shortcode = item.Code
			if len(item.ImageVersions.Candidates) > 0 {
				edge.Node.DisplayURL = item.ImageVersions.Candidates[0].URL
			}
			if item.MediaType == 2 && len(item.VideoVersions) > 0 {
				edge.Node.IsVideo = true
				edge.Node.VideoURL = item.VideoVersions[0].URL
			}
			if len(item.CarouselMedia) > 0 {
				for _, cm := range item.CarouselMedia {
					var cEdge struct {
						Node struct {
							ID         string `json:"id"`
							DisplayURL string `json:"display_url"`
							IsVideo    bool   `json:"is_video"`
							VideoURL   string `json:"video_url"`
						} `json:"node"`
					}
					cEdge.Node.ID = cm.ID
					if len(cm.ImageVersions.Candidates) > 0 {
						cEdge.Node.DisplayURL = cm.ImageVersions.Candidates[0].URL
					}
					if cm.MediaType == 2 && len(cm.VideoVersions) > 0 {
						cEdge.Node.IsVideo = true
						cEdge.Node.VideoURL = cm.VideoVersions[0].URL
					}
					edge.Node.EdgeSidecarToChildren.Edges = append(edge.Node.EdgeSidecarToChildren.Edges, cEdge)
				}
			}
			res.Data.User.EdgeOwnerToTimelineMedia.Edges = append(res.Data.User.EdgeOwnerToTimelineMedia.Edges, edge)
		}

		if !fRes.MoreAvailable || fRes.NextMaxID == "" {
			break
		}
		nextMaxID = fRes.NextMaxID
		time.Sleep(250 * time.Millisecond)
	}
}

type ProgressCallback func(tipo string, pagina, coletados, totalEsperado int)

func (c *InstagramClient) PaginacaoSeguidores(userID string, maxTotal int, delay time.Duration, progress ProgressCallback) ([]string, string, error) {
	return c.paginarFriendship(userID, "followers", maxTotal, delay, progress)
}

func (c *InstagramClient) PaginacaoSeguindo(userID string, maxTotal int, delay time.Duration, progress ProgressCallback) ([]string, string, error) {
	return c.paginarFriendship(userID, "following", maxTotal, delay, progress)
}

func (c *InstagramClient) paginarFriendship(userID, endpoint string, maxTotal int, delay time.Duration, progress ProgressCallback) ([]string, string, error) {
	var usernames []string
	seen := make(map[string]bool)
	nextMaxID := ""
	pagina := 0

	for {
		pagina++
		reqURL := fmt.Sprintf("%s/api/v1/friendships/%s/%s/?count=50", BaseURL, userID, endpoint)
		if nextMaxID != "" {
			reqURL += fmt.Sprintf("&max_id=%s", url.QueryEscape(nextMaxID))
		}

		req, err := http.NewRequest("GET", reqURL, nil)
		if err != nil {
			return usernames, "ERRO_REQ", err
		}
		c.applyHeaders(req, fmt.Sprintf("%s/", BaseURL))

		resp, err := c.HTTP.Do(req)
		if err != nil {
			return usernames, "ERRO_HTTP", err
		}

		bodyBytes, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return usernames, "ERRO_BODY", err
		}

		if resp.StatusCode == 400 || resp.StatusCode == 401 || resp.StatusCode == 403 || resp.StatusCode == 429 {
			bodyStr := strings.ToLower(string(bodyBytes))
			if strings.Contains(bodyStr, "consent_required") || strings.Contains(bodyStr, "challenge") || strings.Contains(bodyStr, "login_required") {
				return usernames, "DESAFIO_LOGIN", fmt.Errorf("instagram solicitou checkpoint ou renovação de login")
			}
			if strings.Contains(bodyStr, "protect our community") || strings.Contains(bodyStr, "limit") {
				return usernames, "RESTRITO", fmt.Errorf("instagram restringiu a visualização desta lista")
			}
			return usernames, "BLOQUEADO", fmt.Errorf("resposta HTTP %d ao consultar %s", resp.StatusCode, endpoint)
		}

		var pageRes FriendshipPaginationResponse
		if err := json.Unmarshal(bodyBytes, &pageRes); err != nil {
			return usernames, "ERRO_JSON", fmt.Errorf("falha ao interpretar JSON de %s: %w", endpoint, err)
		}

		novosNestaPagina := 0
		for _, u := range pageRes.Users {
			cleanU := strings.ToLower(strings.TrimSpace(u.Username))
			if cleanU != "" && !seen[cleanU] {
				seen[cleanU] = true
				usernames = append(usernames, cleanU)
				novosNestaPagina++
			}
		}

		if progress != nil {
			progress(endpoint, pagina, len(usernames), maxTotal)
		}

		if pageRes.NextMaxID == "" || novosNestaPagina == 0 {
			break
		}
		if maxTotal > 0 && len(usernames) >= maxTotal {
			break
		}

		nextMaxID = pageRes.NextMaxID

		if delay > 0 {
			time.Sleep(delay)
		}
	}

	return usernames, "SUCESSO", nil
}
