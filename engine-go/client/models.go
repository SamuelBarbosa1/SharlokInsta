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
		PK            interface{} `json:"pk"`
		Username      string      `json:"username"`
		FullName      string      `json:"full_name"`
		ProfilePicURL string      `json:"profile_pic_url"`
		IsPrivate     bool        `json:"is_private"`
		IsVerified    bool        `json:"is_verified"`
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

type UsersSearchResponse struct {
	Users []struct {
		PK            interface{} `json:"pk"`
		ID            string      `json:"id"`
		Username      string      `json:"username"`
		FullName      string      `json:"full_name"`
		IsPrivate     bool        `json:"is_private"`
		IsVerified    bool        `json:"is_verified"`
		ProfilePicURL string      `json:"profile_pic_url"`
	} `json:"users"`
	Status string `json:"status"`
}

type FriendshipShowResponse struct {
	Following       bool   `json:"following"`
	FollowedBy      bool   `json:"followed_by"`
	OutgoingRequest bool   `json:"outgoing_request"`
	IsPrivate       bool   `json:"is_private"`
	Status          string `json:"status"`
}

type MobileUserInfoResponse struct {
	User struct {
		PK              interface{} `json:"pk"`
		Username        string      `json:"username"`
		FullName        string      `json:"full_name"`
		Biography       string      `json:"biography"`
		ExternalURL     string      `json:"external_url"`
		IsPrivate       bool        `json:"is_private"`
		IsVerified      bool        `json:"is_verified"`
		MediaCount      int         `json:"media_count"`
		FollowerCount   int         `json:"follower_count"`
		FollowingCount  int         `json:"following_count"`
		ProfilePicURL   string      `json:"profile_pic_url"`
		HDProfilePicInfo struct {
			URL string `json:"url"`
		} `json:"hd_profile_pic_url_info"`
	} `json:"user"`
	Status string `json:"status"`
}

type UserFeedMobileResponse struct {
	Items []struct {
		ID            string `json:"id"`
		Code          string `json:"code"`
		MediaType     int    `json:"media_type"` // 1=foto, 2=video, 8=carrossel
		ImageVersions struct {
			Candidates []struct {
				URL string `json:"url"`
			} `json:"candidates"`
		} `json:"image_versions2"`
		VideoVersions []struct {
			URL string `json:"url"`
		} `json:"video_versions"`
		CarouselMedia []struct {
			ID            string `json:"id"`
			MediaType     int    `json:"media_type"`
			ImageVersions struct {
				Candidates []struct {
					URL string `json:"url"`
				} `json:"candidates"`
			} `json:"image_versions2"`
			VideoVersions []struct {
				URL string `json:"url"`
			} `json:"video_versions"`
		} `json:"carousel_media"`
	} `json:"items"`
	MoreAvailable bool   `json:"more_available"`
	NextMaxID     string `json:"next_max_id"`
	Status        string `json:"status"`
}

