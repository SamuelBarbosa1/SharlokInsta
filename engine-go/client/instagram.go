package client

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	IGAppID       = "936619743392459"
	DefaultUA     = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
	BaseURL       = "https://www.instagram.com"
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
	reqURL := fmt.Sprintf("%s/api/v1/users/web_profile_info/?username=%s", BaseURL, clean)

	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, err
	}
	c.applyHeaders(req, fmt.Sprintf("%s/%s/", BaseURL, clean))

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("falha na requisição de perfil: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("erro lendo corpo da resposta: %w", err)
	}

	if resp.StatusCode == 404 {
		return nil, fmt.Errorf("perfil @%s não encontrado (404)", clean)
	}
	if resp.StatusCode == 401 || resp.StatusCode == 403 {
		return nil, fmt.Errorf("autenticação negada (HTTP %d). Verifique o SessionID", resp.StatusCode)
	}
	if resp.StatusCode == 429 {
		return nil, fmt.Errorf("rate limit da Meta (HTTP 429: Too Many Requests). O Instagram exige uma pausa antes de consultar este perfil novamente via REST")
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("resposta HTTP %d inesperada da Meta ao consultar perfil", resp.StatusCode)
	}

	var res WebProfileInfoResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, fmt.Errorf("erro decodificando JSON do perfil (status %d): %w", resp.StatusCode, err)
	}

	if res.Data.User.Username == "" {
		if res.Message != "" {
			return nil, fmt.Errorf("instagram retornou: %s", res.Message)
		}
		return nil, fmt.Errorf("dados do usuário vazios. Possível desafio ou bloqueio temporário")
	}

	return &res, nil
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

		if resp.StatusCode == 400 || resp.StatusCode == 403 {
			bodyStr := strings.ToLower(string(bodyBytes))
			if strings.Contains(bodyStr, "consent_required") || strings.Contains(bodyStr, "challenge") {
				return usernames, "DESAFIO_LOGIN", fmt.Errorf("instagram solicitou checkpoint de segurança")
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

