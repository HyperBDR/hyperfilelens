package enroll

import "strings"

func logOKDetail(title, detail string) {
	logOK(joinDetail(title, detail))
}

func logWarnDetail(title, detail string) {
	logWarn(joinDetail(title, detail))
}

func logFailDetail(title, detail string, code int) {
	logFail(joinDetail(title, detail), code)
}

func joinDetail(title, detail string) string {
	title = strings.TrimSpace(title)
	detail = strings.TrimSpace(detail)
	if title == "" {
		return detail
	}
	if detail == "" {
		return title
	}
	return title + " (" + detail + ")"
}
