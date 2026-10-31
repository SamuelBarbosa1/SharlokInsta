package downloader

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"
)

type DownloadItem struct {
	URL      string `json:"url"`
	DestPath string `json:"dest_path"`
	Label    string `json:"label"`
	IsVideo  bool   `json:"is_video"`
}

type DownloadResult struct {
	Item  DownloadItem
	Error error
}

type DownloaderPool struct {
	Concurrency int
	Client      *http.Client
}

func NewDownloaderPool(concurrency int) *DownloaderPool {
	if concurrency <= 0 {
		concurrency = 10
	}
	return &DownloaderPool{
		Concurrency: concurrency,
		Client: &http.Client{
			Timeout: 45 * time.Second,
		},
	}
}

type ProgressFunc func(concluidos, total int, item DownloadItem, err error)

func (p *DownloaderPool) DownloadAll(items []DownloadItem, onProgress ProgressFunc) []DownloadResult {
	total := len(items)
	if total == 0 {
		return nil
	}

	results := make([]DownloadResult, total)
	semaphore := make(chan struct{}, p.Concurrency)
	var wg sync.WaitGroup
	var completedCount int64

	for idx, itm := range items {
		wg.Add(1)
		go func(index int, item DownloadItem) {
			defer wg.Done()
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			err := p.downloadFile(item.URL, item.DestPath)
			results[index] = DownloadResult{Item: item, Error: err}

			current := atomic.AddInt64(&completedCount, 1)
			if onProgress != nil {
				onProgress(int(current), total, item, err)
			}
		}(idx, itm)
	}

	wg.Wait()
	return results
}

func (p *DownloaderPool) downloadFile(fileURL, destPath string) error {
	dir := filepath.Dir(destPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("falha ao criar pasta %s: %w", dir, err)
	}

	req, err := http.NewRequest("GET", fileURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

	resp, err := p.Client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("HTTP status %d", resp.StatusCode)
	}

	out, err := os.Create(destPath)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, resp.Body)
	return err
}

