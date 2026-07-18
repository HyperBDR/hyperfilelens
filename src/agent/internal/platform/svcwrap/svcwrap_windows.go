//go:build windows

package svcwrap

import (
	"context"
	"log/slog"

	"github.com/kardianos/service"
)

const (
	serviceName        = "HyperFileLensAgent"
	serviceDisplayName = "HyperFileLens Agent"
	serviceDescription = "HyperFileLens backup agent (WebSocket control plane and local CLI)"
)

type daemonRunner struct {
	run    func(context.Context) error
	cancel context.CancelFunc
	done   chan struct{}
}

func (d *daemonRunner) Start(service.Service) error {
	ctx, cancel := context.WithCancel(context.Background())
	d.cancel = cancel
	d.done = make(chan struct{})
	go func() {
		defer close(d.done)
		if err := d.run(ctx); err != nil && err != context.Canceled {
			slog.Error("agent service stopped with error", "err", err)
		}
	}()
	return nil
}

func (d *daemonRunner) Stop(service.Service) error {
	if d.cancel != nil {
		d.cancel()
	}
	if d.done != nil {
		<-d.done
	}
	return nil
}

// RunIfService registers with Windows SCM when the process is started as a service.
func RunIfService(run func(context.Context) error) (handled bool, err error) {
	if service.Interactive() {
		return false, nil
	}
	svc, err := service.New(&daemonRunner{run: run}, &service.Config{
		Name:        serviceName,
		DisplayName: serviceDisplayName,
		Description: serviceDescription,
	})
	if err != nil {
		return false, err
	}
	return true, svc.Run()
}
