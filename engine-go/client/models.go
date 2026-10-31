package client

type WebProfileInfoResponse struct {
	Data struct {
		User struct {
			ID                 string `json:"id"`
			Username           string `json:"username"`
			FullName           string `json:"full_name"`
			Biography          string `json:"biography"`
			ExternalURL        string `json:"external_url"`
			ProfilePicURLHD    string `json:"profile_pic_url_hd"`
			ProfilePicURL      string `json:"profile_pic_url"`
			IsPrivate          bool   `json:"is_private"`
			IsVerified         bool   `json:"is_verified"`
			FollowedByViewer   bool   `json:"followed_by_viewer"`
			RequestedByViewer  bool   `json:"requested_by_viewer"`
			EdgeFollowedBy struct {
				Count int `json:"count"`
			} `json:"edge_followed_by"`
			EdgeFollow struct {
				Count int `json:"count"`
			} `json:"edge_follow"`
			EdgeOwnerToTimelineMedia struct {
				Count int `json:"count"`
				PageInfo struct {
					HasNextPage bool   `json:"has_next_page"`
					EndCursor   string `json:"end_cursor"`
				} `json:"page_info"`
				Edges []struct {
					Node struct {
						ID           string `json:"id"`
						Shortcode    string `json:"shortcode"`
						DisplayURL   string `json:"display_url"`
						IsVideo      bool   `json:"is_video"`
						VideoURL     string `json:"video_url"`
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
				} `json:"edges"`
			} `json:"edge_owner_to_timeline_media"`
		} `json:"user"`
	} `json:"data"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type FriendshipPaginationResponse struct {
	Users []struct {
		PK            int64  `json:"pk"`
		Username      string `json:"username"`
		FullName      string `json:"full_name"`
		ProfilePicURL string `json:"profile_pic_url"`
		IsPrivate     bool   `json:"is_private"`
		IsVerified    bool   `json:"is_verified"`
	} `json:"users"`
	NextMaxID string `json:"next_max_id"`
	BigList   bool   `json:"big_list"`
	Status    string `json:"status"`
	Message   string `json:"message"`
}

type StoryItem struct {
	ID        string `json:"id"`
	MediaURL  string `json:"media_url"`
	IsVideo   bool   `json:"is_video"`
	TakenAt   int64  `json:"taken_at"`
	Highlight string `json:"highlight,omitempty"`
}

type HighlightsTrayResponse struct {
	Tray []struct {
		ID    string `json:"id"`
		Title string `json:"title"`
	} `json:"tray"`
	Status string `json:"status"`
}

