import { ArrowLeftRight, FolderOpen, FolderTree, Router, Server } from 'lucide-vue-next'
import type { Component } from 'vue'

export type NasMountProtocol = 'smb' | 'nfs'

export const sourceAgentSidebarIcon: Component = ArrowLeftRight

export const dataGatewaySidebarIcon: Component = Router

export const targetNasSidebarIcon: Component = Server

export const nasProtocolSmbIcon: Component = FolderOpen

export const nasProtocolNfsIcon: Component = FolderTree

export function nasMountProtocolIcon(protocol: NasMountProtocol | string | undefined): Component {
  return protocol === 'nfs' ? nasProtocolNfsIcon : nasProtocolSmbIcon
}
