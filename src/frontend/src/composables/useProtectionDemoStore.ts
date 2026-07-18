import { reactive, ref } from 'vue'
import { logger } from '../lib/logger'
import type { CompressionLevel } from '../lib/protectionBackupConfigApi'

const DEMO_DATA_ENABLED =
  import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEMO_DATA === 'true'

export type DemoNodeState = 'online' | 'offline'

export type DemoHost = {
  id: string
  name: string
  hostname: string
  nodeName?: string
  nodeIp?: string
  status?: DemoNodeState
  registeredAt?: string
}

export type DemoNas = {
  id: string
  name: string
  hostname: string
  protocol?: 'nfs' | 'smb'
  proxyNodeName?: string
  proxyNodeIp?: string
  status?: DemoNodeState
  registeredAt?: string
}

export type DemoSourceOption = { hostId: string; path: string; label: string }

export type DemoTarget = {
  id: string
  name: string
  location: string
  repoType: string
  status?: 'online' | 'warning' | 'offline'
  usedBytes?: number
  capacityBytes?: number
}

export type DemoPolicy = {
  id: string
  name: string
  schedule: string
  backupFrequencyDesc: string
  retentionDesc: string
}

export type DemoGlobalFilter = {
  id: string
  name: string
  summary: string
}

export type BackupStatus = 'idle' | 'backing_up' | 'completed' | 'failed'
export type DemoPathType = 'directory' | 'file' | 'unknown'

export type DemoSnapshotDir = {
  hostId: string
  hostName: string
  path: string
  pathType?: DemoPathType
  sizeBytes: number
  fileCount: number
  innerDirCount: number
}

export type DemoFsNode = {
  name: string
  type: 'file' | 'dir'
  children?: DemoFsNode[]
}

export type DemoSnapshot = {
  id: string
  startTime: string
  endTime: string
  status?: string
  sizeBytes: number
  fileCount: number
  dirCount: number
  dirs: DemoSnapshotDir[]
  treeByPath: Record<string, DemoFsNode[]>
}

export type DemoBackup = {
  id: string
  name: string
  remark: string
  policyId: string
  globalFilterId: string
  globalFilterIds?: string[]
  compressionLevel?: CompressionLevel
  targetId: string
  sources: { hostId: string; path: string; pathType?: DemoPathType }[]
  status: BackupStatus
  latestSnapshotAt: string | null
  snapshots: DemoSnapshot[]
}

const DEMO_HOSTS: DemoHost[] = [
  { id: 'h1', name: 'Production Web-01', hostname: 'web-01.prod.internal', nodeName: 'Production Web-01', nodeIp: '10.20.1.21', status: 'online', registeredAt: '2026-04-18 09:16:00' },
  { id: 'h2', name: 'Production DB-02', hostname: 'db-02.prod.internal', nodeName: 'Production DB-02', nodeIp: '10.20.1.22', status: 'online', registeredAt: '2026-04-20 13:40:00' },
  { id: 'h3', name: 'Archive Node', hostname: 'archive-01.internal', nodeName: 'Archive Node', nodeIp: '10.20.1.23', status: 'offline', registeredAt: '2026-04-26 18:05:00' },
  { id: 'h4', name: 'Finance Share Host', hostname: 'finance-share-01.internal', nodeName: 'Finance Share Host', nodeIp: '10.20.1.24', status: 'online', registeredAt: '2026-04-28 11:12:00' },
  { id: 'h5', name: 'Design Assets Node', hostname: 'design-assets-01.internal', nodeName: 'Design Assets Node', nodeIp: '10.20.1.25', status: 'online', registeredAt: '2026-05-02 15:30:00' },
]

const DEMO_NAS: DemoNas[] = [
  { id: 'nas1', name: 'NAS-Storage-A', hostname: 'nas-a.corp.local', protocol: 'nfs', proxyNodeName: 'Proxy-GW-01', proxyNodeIp: '172.16.1.10', status: 'online', registeredAt: '2026-04-10 08:20:00' },
  { id: 'nas2', name: 'NAS-Archive-B', hostname: 'nas-b.corp.local', protocol: 'smb', proxyNodeName: 'Proxy-GW-02', proxyNodeIp: '172.16.1.11', status: 'online', registeredAt: '2026-04-12 10:35:00' },
  { id: 'nas3', name: 'NAS-Project-Share-C', hostname: 'nas-c.corp.local', protocol: 'nfs', proxyNodeName: 'Proxy-GW-Archive', proxyNodeIp: '172.16.1.15', status: 'offline', registeredAt: '2026-04-08 16:50:00' },
]

const DEMO_TARGETS: DemoTarget[] = [
  { id: 't1', name: 'Object Storage Bucket A (East)', location: 's3://hfl-backup-hz-a', repoType: 'S3', status: 'online', usedBytes: 18 * 1024 ** 4, capacityBytes: 80 * 1024 ** 4 },
  { id: 't2', name: 'NAS Backup Repository B', location: 'nfs://nas-backup/vol1/hfl', repoType: 'NAS', status: 'online', usedBytes: 42 * 1024 ** 4, capacityBytes: 96 * 1024 ** 4 },
  { id: 't3', name: 'Azure Blob Archive West', location: 'https://acct.blob.core.windows.net/hfl-archive', repoType: 'Azure Blob', status: 'warning', usedBytes: 112 * 1024 ** 4, capacityBytes: 128 * 1024 ** 4 },
  { id: 't4', name: 'GCS Standard Bucket EU', location: 'gs://hfl-backup-eu-01', repoType: 'GCS', status: 'online', usedBytes: 9 * 1024 ** 4, capacityBytes: 64 * 1024 ** 4 },
  { id: 't5', name: 'Local S3-Compatible Repository', location: 's3://s3-local:9000/hfl-prod', repoType: 'S3', status: 'online', usedBytes: 28 * 1024 ** 4, capacityBytes: 48 * 1024 ** 4 },
  { id: 't6', name: 'SMB File Share Backup', location: 'smb://filer01.corp/backup/hfl', repoType: 'SMB', status: 'offline', usedBytes: 31 * 1024 ** 4, capacityBytes: 40 * 1024 ** 4 },
  { id: 't7', name: 'Managed WebDAV Repository', location: 'https://dav.provider.net/hfl-repo', repoType: 'WebDAV', status: 'warning', usedBytes: 17 * 1024 ** 4, capacityBytes: 24 * 1024 ** 4 },
]

const DEMO_GLOBAL_FILTERS: DemoGlobalFilter[] = [
  {
    id: 'gf1',
    name: 'Development Dependencies and Repository Metadata',
    summary: '**/node_modules/**, **/.git/**; ignore common cache directories',
  },
  {
    id: 'gf2',
    name: 'Linux Builds and Large Files',
    summary: 'Linux; cache directories; skip files larger than 512 MB',
  },
]

const DEMO_POLICIES: DemoPolicy[] = [
  {
    id: 'p1',
    name: 'Daily Full Backup',
    schedule: '0 2 * * *',
    backupFrequencyDesc: 'Create a full snapshot daily at 02:00 (Cron: 0 2 * * *).',
    retentionDesc: 'Keep the latest 10 restore points; hourly for days 0–2, daily for days 2–30, then monthly.',
  },
  {
    id: 'p2',
    name: 'Weekday Incremental Every 4 Hours',
    schedule: '0 */4 * * 1-5',
    backupFrequencyDesc: 'Create an incremental snapshot every four hours on weekdays (Cron: 0 */4 * * 1-5).',
    retentionDesc: 'Keep the latest 24 restore points, dense short-term points, and daily month-end snapshots.',
  },
  {
    id: 'p3',
    name: 'Weekend Archive',
    schedule: '0 3 * * 6',
    backupFrequencyDesc: 'Create an archive snapshot every Saturday at 03:00 (Cron: 0 3 * * 6).',
    retentionDesc: 'Prioritize long-term retention and keep archive data monthly after 90 days.',
  },
]

const treeFor = (path: string): DemoFsNode[] => {
  if (path.includes('/data/www')) {
    return [
      { name: 'index.html', type: 'file' },
      {
        name: 'assets',
        type: 'dir',
        children: [
          { name: 'app.js', type: 'file' },
          { name: 'chunk-vendors.js', type: 'file' },
        ],
      },
      { name: 'config.json', type: 'file' },
    ]
  }
  if (path.includes('/var/lib/pg')) {
    return [
      { name: 'base', type: 'dir', children: [{ name: '16384', type: 'dir', children: [{ name: '1247', type: 'file' }] }] },
      { name: 'global', type: 'dir', children: [{ name: 'pg_control', type: 'file' }] },
    ]
  }
  return [
    { name: 'README.txt', type: 'file' },
    { name: 'logs', type: 'dir', children: [{ name: 'app.log', type: 'file' }, { name: 'error.log', type: 'file' }] },
  ]
}

function seedBackups(): DemoBackup[] {
  const webDir: DemoSnapshotDir = {
    hostId: 'h1',
    hostName: 'Production Web-01',
    path: '/data/www/app',
    sizeBytes: 18_452_335_616,
    fileCount: 76_200,
    innerDirCount: 3_100,
  }
  const dbDir: DemoSnapshotDir = {
    hostId: 'h2',
    hostName: 'Production DB-02',
    path: '/var/lib/pg/data',
    sizeBytes: 24_433_787_904,
    fileCount: 52_200,
    innerDirCount: 6_100,
  }
  const webStaticDir: DemoSnapshotDir = {
    hostId: 'h1',
    hostName: 'Production Web-01',
    path: '/data/www/static',
    sizeBytes: 4_280_000_000,
    fileCount: 12_400,
    innerDirCount: 820,
  }
  const webNginxLogDir: DemoSnapshotDir = {
    hostId: 'h1',
    hostName: 'Production Web-01',
    path: '/var/log/nginx',
    sizeBytes: 512_000_000,
    fileCount: 3_200,
    innerDirCount: 48,
  }
  const archiveDir: DemoSnapshotDir = {
    hostId: 'h3',
    hostName: 'Archive Node',
    path: '/archive/project-docs',
    sizeBytes: 8_900_000_000,
    fileCount: 45_000,
    innerDirCount: 1_200,
  }

  function makeSnapshot(
    id: string,
    startTime: string,
    endTime: string,
    sizeBytes: number,
    fileCount: number,
    dirCount: number,
    dir: DemoSnapshotDir,
  ): DemoSnapshot {
    return {
      id,
      startTime,
      endTime,
      sizeBytes,
      fileCount,
      dirCount,
      dirs: [dir],
      treeByPath: {
        [dir.path]: treeFor(dir.path),
      },
    }
  }

  const snap1 = makeSnapshot(
    's-seed-1',
    '2026-05-10T01:58:10+08:00',
    '2026-05-10T02:12:44+08:00',
    18_452_335_616,
    76_200,
    3_100,
    webDir,
  )
  const snap2 = makeSnapshot(
    's-seed-2',
    '2026-05-09T01:55:00+08:00',
    '2026-05-09T02:08:22+08:00',
    17_980_000_000,
    74_900,
    3_060,
    webDir,
  )
  const snap3 = makeSnapshot(
    's-seed-3',
    '2026-05-10T02:18:00+08:00',
    '2026-05-10T02:31:36+08:00',
    24_433_787_904,
    52_200,
    6_100,
    dbDir,
  )
  const snap4 = makeSnapshot(
    's-seed-4',
    '2026-05-09T02:14:10+08:00',
    '2026-05-09T02:27:02+08:00',
    23_980_000_000,
    51_700,
    6_040,
    dbDir,
  )
  const snap5 = makeSnapshot(
    's-seed-5',
    '2026-05-08T20:00:00+08:00',
    '2026-05-08T20:06:18+08:00',
    8_900_000_000,
    45_000,
    1_200,
    archiveDir,
  )
  const snap6 = makeSnapshot(
    's-seed-6',
    '2026-05-10T02:20:00+08:00',
    '2026-05-10T02:24:18+08:00',
    4_280_000_000,
    12_400,
    820,
    webStaticDir,
  )
  const snap7 = makeSnapshot(
    's-seed-7',
    '2026-05-10T01:40:00+08:00',
    '2026-05-10T01:42:55+08:00',
    512_000_000,
    3_200,
    48,
    webNginxLogDir,
  )

  const b1: DemoBackup = {
    id: 'b-seed-1',
    name: 'Core Web Application Backup',
    remark: 'Runs during the nightly window for web application directories.',
    policyId: 'p1',
    globalFilterId: 'gf1',
    compressionLevel: 'balanced',
    targetId: 't1',
    sources: [{ hostId: 'h1', path: '/data/www/app' }],
    status: 'completed',
    latestSnapshotAt: snap1.endTime,
    snapshots: [snap1, snap2],
  }

  const b2: DemoBackup = {
    id: 'b-seed-2',
    name: 'Core Database Backup',
    remark: 'Runs during the nightly window for PostgreSQL data directories.',
    policyId: 'p1',
    globalFilterId: 'gf2',
    compressionLevel: 'balanced',
    targetId: 't1',
    sources: [{ hostId: 'h2', path: '/var/lib/pg/data' }],
    status: 'completed',
    latestSnapshotAt: snap3.endTime,
    snapshots: [snap3, snap4],
  }

  const b3: DemoBackup = {
    id: 'b-seed-3',
    name: 'Project Document Archive',
    remark: 'Weekend-only policy with a failed state for UI demonstrations.',
    policyId: 'p3',
    globalFilterId: '',
    compressionLevel: 'high',
    targetId: 't2',
    sources: [{ hostId: 'h3', path: '/archive/project-docs' }],
    status: 'failed',
    latestSnapshotAt: snap5.endTime,
    snapshots: [snap5],
  }

  const b4: DemoBackup = {
    id: 'b-seed-4',
    name: 'Web Static Asset Backup',
    remark: 'Uses the main application policy and demonstrates multiple directories per source.',
    policyId: 'p1',
    globalFilterId: 'gf1',
    compressionLevel: 'balanced',
    targetId: 't1',
    sources: [{ hostId: 'h1', path: '/data/www/static' }],
    status: 'completed',
    latestSnapshotAt: snap6.endTime,
    snapshots: [snap6],
  }

  const b5: DemoBackup = {
    id: 'b-seed-5',
    name: 'Web Nginx Log Backup',
    remark: 'Writes logs to a local S3-compatible repository and demonstrates multiple targets.',
    policyId: 'p2',
    globalFilterId: '',
    compressionLevel: 'balanced',
    targetId: 't5',
    sources: [{ hostId: 'h1', path: '/var/log/nginx' }],
    status: 'completed',
    latestSnapshotAt: snap7.endTime,
    snapshots: [snap7],
  }

  const financePaths = [
    '/srv/finance/reports',
    '/srv/finance/contracts',
    '/srv/finance/invoices/2025',
    '/srv/finance/invoices/2024',
    '/srv/finance/payroll',
    '/srv/finance/tax',
    '/srv/finance/audit',
    '/srv/finance/archive',
    '/srv/finance/exports/daily',
    '/srv/finance/exports/monthly',
  ]
  const financeBackups: DemoBackup[] = financePaths.map((path, index) => {
    const dir: DemoSnapshotDir = {
      hostId: 'h4',
      hostName: 'Finance Share Host',
      path,
      sizeBytes: 800_000_000 + index * 120_000_000,
      fileCount: 8_000 + index * 600,
      innerDirCount: 200 + index * 30,
    }
    const snap = makeSnapshot(
      `s-seed-fin-${index + 1}`,
      `2026-05-09T0${index % 9}:10:00+08:00`,
      `2026-05-09T0${index % 9}:18:00+08:00`,
      dir.sizeBytes,
      dir.fileCount,
      dir.innerDirCount,
      dir,
    )
    const targetIds = ['t1', 't2', 't5', 't6'] as const
    return {
      id: `b-seed-fin-${index + 1}`,
      name: `Finance Share · ${path.split('/').pop() || path}`,
      remark: 'Demonstrates collapsed directories and popover expansion for a large source.',
      policyId: index % 2 === 0 ? 'p1' : 'p2',
      globalFilterId: index % 3 === 0 ? 'gf1' : '',
      compressionLevel: index % 4 === 0 ? 'high' : 'balanced',
      targetId: targetIds[index % targetIds.length],
      sources: [{ hostId: 'h4', path }],
      status: 'completed' as const,
      latestSnapshotAt: snap.endTime,
      snapshots: [snap],
    }
  })

  return [b1, b2, b3, b4, b5, ...financeBackups]
}

const DEMO_HOST_SOURCE_PATH_SEEDS: Record<string, string[]> = {
  h1: ['/data/www/app', '/data/www/static', '/var/log/nginx'],
  h2: ['/var/lib/pg/data', '/etc/postgresql'],
  h3: ['/archive/project-docs', '/archive/legal'],
  h4: [
    '/srv/finance/reports',
    '/srv/finance/contracts',
    '/srv/finance/invoices/2025',
    '/srv/finance/invoices/2024',
    '/srv/finance/payroll',
    '/srv/finance/tax',
    '/srv/finance/audit',
    '/srv/finance/archive',
    '/srv/finance/exports/daily',
    '/srv/finance/exports/monthly',
  ],
  h5: ['/data/design/raw', '/data/design/exports'],
}

const DEMO_NAS_SOURCE_PATH_SEEDS: Record<string, string[]> = {
  nas1: ['/volume1/shared/docs', '/volume1/shared/media', '/volume1/backup/db_dumps'],
  nas2: ['/volume2/archive/reports', '/volume2/archive/photos'],
  nas3: ['/volume3/projects/team-share', '/volume3/projects/releases'],
}

export const DEMO_HOST_SOURCE_PATHS: Record<string, string[]> =
  DEMO_DATA_ENABLED ? DEMO_HOST_SOURCE_PATH_SEEDS : {}

export const DEMO_NAS_SOURCE_PATHS: Record<string, string[]> =
  DEMO_DATA_ENABLED ? DEMO_NAS_SOURCE_PATH_SEEDS : {}

export type DemoDirTreeItem = {
  label: string
  path: string
  isLeaf: boolean
}

function ancestorsOfPath(path: string): string[] {
  const parts = path.split('/').filter(Boolean)
  const accs: string[] = []
  let cur = ''
  for (const p of parts) {
    cur = `${cur}/${p}`
    accs.push(cur)
  }
  return accs
}

function dirClosureForHost(hostId: string): Set<string> {
  const set = new Set<string>()
  for (const leaf of DEMO_HOST_SOURCE_PATHS[hostId] || []) {
    for (const a of ancestorsOfPath(leaf)) {
      set.add(a)
    }
  }
  return set
}

function dirClosureForNas(nasId: string): Set<string> {
  const set = new Set<string>()
  for (const leaf of DEMO_NAS_SOURCE_PATHS[nasId] || []) {
    for (const a of ancestorsOfPath(leaf)) {
      set.add(a)
    }
  }
  return set
}

function directChildDirs(all: Set<string>, parentPath: string): string[] {
  const p = parentPath.replace(/\/$/, '') || ''
  const out: string[] = []
  for (const full of all) {
    if (full === p) continue
    if (p === '') {
      if (!/^\/[^/]+$/.test(full)) continue
    } else if (!full.startsWith(`${p}/`)) {
      continue
    } else {
      const rel = full.slice(p.length + 1)
      if (rel.includes('/')) continue
    }
    out.push(full)
  }
  return [...new Set(out)].sort()
}

function hasChildDirsUnder(all: Set<string>, dir: string): boolean {
  const prefix = dir.endsWith('/') ? dir : `${dir}/`
  for (const x of all) {
    if (x !== dir && x.startsWith(prefix)) return true
  }
  return false
}

export function listDirChildrenDemo(hostId: string, parentPath: string): Promise<DemoDirTreeItem[]> {
  if (!DEMO_DATA_ENABLED) return Promise.resolve([])
  return new Promise((resolve) => {
    const delay = 100 + Math.floor(Math.random() * 180)
    window.setTimeout(() => {
      const all = dirClosureForHost(hostId)
      const paths = directChildDirs(all, parentPath)
      const items: DemoDirTreeItem[] = paths.map((path) => ({
        label: path.split('/').filter(Boolean).pop() ?? path,
        path,
        isLeaf: !hasChildDirsUnder(all, path),
      }))
      resolve(items)
    }, delay)
  })
}

export function listNasDirChildrenDemo(nasId: string, parentPath: string): Promise<DemoDirTreeItem[]> {
  if (!DEMO_DATA_ENABLED) return Promise.resolve([])
  return new Promise((resolve) => {
    const delay = 100 + Math.floor(Math.random() * 180)
    window.setTimeout(() => {
      const all = dirClosureForNas(nasId)
      const paths = directChildDirs(all, parentPath)
      const items: DemoDirTreeItem[] = paths.map((path) => ({
        label: path.split('/').filter(Boolean).pop() ?? path,
        path,
        isLeaf: !hasChildDirsUnder(all, path),
      }))
      resolve(items)
    }, delay)
  })
}

const sourceOptions = (): DemoSourceOption[] => {
  if (!DEMO_DATA_ENABLED) return []
  const out: DemoSourceOption[] = []
  for (const h of DEMO_HOSTS) {
    for (const path of DEMO_HOST_SOURCE_PATHS[h.id] || []) {
      out.push({
        hostId: h.id,
        path,
        label: `${h.name} · ${path}`,
      })
    }
  }
  return out
}

const backups = ref<DemoBackup[]>(DEMO_DATA_ENABLED ? seedBackups() : [])

let storeWarned = false

export function useProtectionDemoStore() {
  const hosts = ref(DEMO_DATA_ENABLED ? [...DEMO_HOSTS] : [])
  const nas = ref(DEMO_DATA_ENABLED ? [...DEMO_NAS] : [])
  const targets = ref(DEMO_DATA_ENABLED ? [...DEMO_TARGETS] : [])
  const policies = reactive(DEMO_DATA_ENABLED ? [...DEMO_POLICIES] : [])
  const globalFilters = reactive(DEMO_DATA_ENABLED ? [...DEMO_GLOBAL_FILTERS] : [])
  const sourceOptionsList = sourceOptions()

  function warnOnce() {
    if (!DEMO_DATA_ENABLED) return
    if (storeWarned) return
    storeWarned = true
    if (import.meta.env.DEV) {
      logger.info('useProtectionDemoStore.ts', 600, 'The data-protection page is using in-memory demo data.')
    }
  }

  function getBackup(id: string) {
    return backups.value.find((b) => b.id === id)
  }

  function getPolicy(id: string | undefined | null) {
    if (id === undefined || id === null || id === '') return undefined
    return policies.find((p) => p.id === id)
  }

  function addPolicy(policy: DemoPolicy) {
    policies.push(policy)
  }

  function getGlobalFilter(id: string | undefined | null) {
    if (id === undefined || id === null || id === '') return undefined
    return globalFilters.find((g) => g.id === id)
  }

  function addGlobalFilter(filter: DemoGlobalFilter) {
    globalFilters.push(filter)
  }

  function getTarget(id: string) {
    return targets.value.find((t) => t.id === id)
  }

  function addTarget(t: DemoTarget) {
    targets.value = [...targets.value, t]
  }

  function getHost(id: string) {
    return hosts.value.find((h) => h.id === id)
  }

  function getNas(id: string) {
    return nas.value.find((n) => n.id === id)
  }

  function getNodeName(id: string): string {
    const h = getHost(id)
    if (h) return h.name
    const n = getNas(id)
    if (n) return n.name
    return id
  }

  function getPathsForHost(hostId: string): string[] {
    return DEMO_HOST_SOURCE_PATHS[hostId] ? [...DEMO_HOST_SOURCE_PATHS[hostId]] : []
  }

  function listDirChildren(hostId: string, parentPath: string): Promise<DemoDirTreeItem[]> {
    return listDirChildrenDemo(hostId, parentPath)
  }

  function listNasDirChildren(nasId: string, parentPath: string): Promise<DemoDirTreeItem[]> {
    return listNasDirChildrenDemo(nasId, parentPath)
  }

  function removeBackups(ids: string[]) {
    const set = new Set(ids)
    backups.value = backups.value.filter((b) => !set.has(b.id))
  }

  function updateBackup(
    id: string,
    patch: Partial<Pick<DemoBackup, 'name' | 'remark' | 'policyId' | 'globalFilterId' | 'status' | 'latestSnapshotAt'>>,
  ) {
    const b = backups.value.find((x) => x.id === id)
    if (!b) return
    Object.assign(b, patch)
  }

  function appendSnapshot(backupId: string, snap: DemoSnapshot) {
    const b = backups.value.find((x) => x.id === backupId)
    if (!b) return
    b.snapshots = [snap, ...b.snapshots]
    b.latestSnapshotAt = snap.endTime
    b.status = 'completed'
  }

  function removeSnapshot(backupId: string, snapshotId: string) {
    const b = backups.value.find((x) => x.id === backupId)
    if (!b) return false
    const idx = b.snapshots.findIndex((s) => s.id === snapshotId)
    if (idx === -1) return false
    b.snapshots.splice(idx, 1)
    const newest = b.snapshots.reduce<DemoSnapshot | null>((best, s) => {
      if (!best) return s
      return s.endTime > best.endTime ? s : best
    }, null)
    b.latestSnapshotAt = newest?.endTime ?? null
    return true
  }

  function addBackup(row: DemoBackup) {
    backups.value = [row, ...backups.value]
  }

  function addHost(host: DemoHost) {
    hosts.value.push(host)
  }

  function addNas(item: DemoNas) {
    nas.value.push(item)
  }

  function removeSources(sourceIds: string[]) {
    const set = new Set(sourceIds)
    if (!set.size) return
    hosts.value = hosts.value.filter((h) => !set.has(h.id))
    nas.value = nas.value.filter((n) => !set.has(n.id))
    backups.value = backups.value.filter((b) => !b.sources.some((s) => set.has(s.hostId)))
  }

  return {
    hosts,
    nas,
    targets,
    policies,
    globalFilters,
    sourceOptionsList,
    backups,
    warnOnce,
    getBackup,
    getPolicy,
    getGlobalFilter,
    getTarget,
    getHost,
    getNas,
    getNodeName,
    getPathsForHost,
    listDirChildren,
    listNasDirChildren,
    removeBackups,
    updateBackup,
    appendSnapshot,
    removeSnapshot,
    addBackup,
    addTarget,
    addGlobalFilter,
    addPolicy,
    addHost,
    addNas,
    removeSources,
  }
}
