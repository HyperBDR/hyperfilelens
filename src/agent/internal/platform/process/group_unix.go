//go:build unix

package process

import (
	"os"
	"os/exec"
	"syscall"
)

func configureProcessGroup(cmd *exec.Cmd) {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.Setpgid = true
}

func killProcessGroup(proc *os.Process) {
	if proc == nil {
		return
	}
	_ = syscall.Kill(-proc.Pid, syscall.SIGKILL)
}
