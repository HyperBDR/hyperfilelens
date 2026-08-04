package enrollmentclient

import "encoding/json"

// decodeAPIData peels the standard console {code,message,data} envelope when present.
func decodeAPIData(raw []byte) (map[string]any, error) {
	var parsed map[string]any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, err
	}
	if nested, ok := parsed["data"].(map[string]any); ok {
		return nested, nil
	}
	return parsed, nil
}

func stringField(data map[string]any, key string) string {
	value, _ := data[key].(string)
	return value
}

func boolField(data map[string]any, key string) bool {
	value, _ := data[key].(bool)
	return value
}
