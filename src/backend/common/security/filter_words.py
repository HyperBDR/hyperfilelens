"""
Default content filter word list (platform-level).

This is intentionally separate from HTTP response constants, so that
application-level policy can evolve without polluting transport concerns.
"""

BASE_FILTER_WORDS = [
    "vpn",
    "vmess",
    "v2ray",
    "shadowrocket",
    "shadowsocks",
    "wireguard",
    "openvpn",
    "tor browser",
    "nsfw",
]
