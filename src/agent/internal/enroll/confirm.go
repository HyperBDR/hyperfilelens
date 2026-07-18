package enroll

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"github.com/mattn/go-isatty"
)

// confirmAction prompts on a TTY unless autoYes is set.
func confirmAction(message string, autoYes bool) error {
	if autoYes {
		return nil
	}
	if !isatty.IsTerminal(os.Stdin.Fd()) {
		return fmt.Errorf("Confirmation is required but no interactive terminal was detected. Re-run in an interactive shell or pass --yes.")
	}
	logInfo(message)
	fmt.Print("Continue? [y/N] ")
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("Operation was cancelled.")
	}
	ans := strings.ToLower(strings.TrimSpace(line))
	if ans == "y" || ans == "yes" {
		return nil
	}
	return fmt.Errorf("Operation was cancelled.")
}
