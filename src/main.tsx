import { useEffect, useMemo, useRef, useState } from 'react'
import type { ComponentType, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  CalendarDays,
  Crosshair,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardCheck,
  Cloud,
  Clock3,
  Database,
  Droplets,
  Download,
  FileUp,
  FileText,
  Filter,
  Gauge,
  History,
  Layers3,
  LayoutDashboard,
  LocateFixed,
  LogIn,
  LogOut,
  Mail,
  MapPin,
  MapPinned,
  MessageSquare,
  Moon,
  Menu,
  Minus,
  MoreHorizontal,
  Phone,
  Play,
  Radio,
  RefreshCw,
  Save,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sun,
  SlidersHorizontal,
  Thermometer,
  Upload,
  UserCheck,
  UserPlus,
  Users,
  Waves,
  X,
  Zap,
} from 'lucide-react'
// The advisor uses a restrained conversation icon rather than decorative AI sparkles.
const Sparkles = MessageSquare
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './styles.css'

type Page = 'overview' | 'live' | 'quality' | 'level' | 'advisor' | 'history' | 'devices' | 'alerts' | 'map' | 'reports' | 'education' | 'settings' | 'help' | 'profile' | 'admin' | 'submit' | 'submissions' | 'notifications' | 'privacy' | 'terms'
type Status = 'within' | 'marginal' | 'exceeds'
type Theme = 'dark' | 'light'
type Role = 'admin' | 'user'
type AuthMode = 'signin' | 'signup' | 'forgot'

type LocationContext = {
  label: string
  country?: string
  state?: string
  district?: string
  city?: string
  postcode?: string
}

type LiveLocation = {
  latitude: number
  longitude: number
  accuracy: number
  updatedAt: string
  place?: LocationContext
}

type LocationSearchResult = {
  place_id: number | string
  display_name: string
  lat: string
  lon: string
  address?: Record<string, string>
}

type Account = {
  id: string
  name: string
  email: string
  mobileNumber?: string
  emailVerified?: boolean
  mobileVerified?: boolean
  reminderConsent?: boolean
  preferredReminderChannel?: 'email' | 'sms' | 'both'
  timezone?: string
  role: Role
  lastLocation: LiveLocation | null
}

type QualityUpdate = {
  id: string
  userName: string
  role: Role
  values: Record<string, number>
  location: LiveLocation | null
  createdAt: string
  status: 'pending' | 'reviewed'
}

type DashboardSnapshot = {
  status: string
  measurement_count: number
  station_count: number
  device_count: number
  online_devices: number
  latest_measurement?: { timestamp?: string; source?: string; quality_status?: string } | null
  latest_quality?: { measured_at?: string; classification?: string | null; wqi?: number | null; data_quality?: string } | null
  forecast?: { model_name?: string; horizon_days?: number; confidence?: number | null } | null
}

type ParameterConfig = {
  key: string
  name: string
  short: string
  unit: string
  precision: number
  min: number
  max: number
  standard: { good: number; warn: number; direction: 'high' | 'low' | 'range'; lower?: number; upper?: number }
  color: string
  icon: ComponentType<{ size?: number; strokeWidth?: number }>
}

// Replace this profile with model.feature_names_in_ and the serialized model metadata.
const parameterConfig: ParameterConfig[] = [
  { key: 'pH', name: 'pH', short: 'pH', unit: 'pH', precision: 2, min: 0, max: 14, standard: { good: 8.5, warn: 9.5, direction: 'range', lower: 6.5, upper: 8.5 }, color: '#222222', icon: Droplets },
  { key: 'TDS_mg_L', name: 'TDS', short: 'TDS', unit: 'ppm', precision: 0, min: 0, max: 10000, standard: { good: 500, warn: 2000, direction: 'high' }, color: '#555555', icon: Activity },
  { key: 'turbidity_ntu', name: 'Turbidity', short: 'Turbidity', unit: 'NTU', precision: 1, min: 0, max: 4000, standard: { good: 5, warn: 25, direction: 'high' }, color: '#888888', icon: Waves },
  { key: 'temperature_c', name: 'Temperature', short: 'Temp', unit: '°C', precision: 1, min: -10, max: 80, standard: { good: 30, warn: 40, direction: 'high' }, color: '#aaaaaa', icon: Zap },
]

// Demo labels are intentionally explicit until the real model artifact is supplied.
const modelProfile = {
  version: 'screening-wqi-0.2',
  classes: ['Excellent', 'Good', 'Poor', 'Very poor', 'Unsuitable'],
  featureOrder: parameterConfig.map((parameter) => parameter.key),
  source: 'Four-parameter calibrated screening model: pH, TDS (ppm), turbidity (NTU), and temperature-compensated readings',
}

const initialValues: Record<string, number> = {
  pH: 7.34,
  TDS_mg_L: 284,
  turbidity_ntu: 2.4,
  temperature_c: 25.0,
}

const storageKey = (key: string) => `hydroinsight:${key}`
const backendUrl = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

function readStorage<T>(key: string, fallback: T): T {
  try {
    const stored = window.localStorage.getItem(storageKey(key))
    return stored ? JSON.parse(stored) as T : fallback
  } catch {
    return fallback
  }
}

function writeStorage(key: string, value: unknown) {
  try {
    window.localStorage.setItem(storageKey(key), JSON.stringify(value))
  } catch {
    return
  }
}

function persistedAccounts(accounts: Account[]) { return accounts }

async function backendAuth(endpoint: 'signup' | 'signin', payload: Record<string, string>) {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const csrf = document.cookie.split('; ').find((item) => item.startsWith('aquasense_csrf='))?.split('=')[1]
  if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf))
  const response = await fetch(`${backendUrl}/api/auth/${endpoint}`, { method: 'POST', headers, body: JSON.stringify(payload), credentials: 'include' })
  const data = await response.json().catch(() => ({})) as { token?: string; user?: { id: string; name: string; email: string; role: Role; mobile_number?: string; email_verified?: boolean; mobile_verified?: boolean; reminder_consent?: boolean; preferred_reminder_channel?: 'email' | 'sms' | 'both'; timezone?: string }; detail?: string }
  if (!response.ok) throw new Error(data.detail || `Backend ${endpoint} failed`)
  const user = data.user
  if (!user) throw new Error('Backend returned an incomplete authentication response')
  return { token: data.token, user }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  const csrf = document.cookie.split('; ').find((item) => item.startsWith('aquasense_csrf='))?.split('=')[1]
  if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf))
  const response = await fetch(`${backendUrl}${path}`, { ...options, headers, credentials: 'include' })
  const data = await response.json().catch(() => ({})) as T & { detail?: string }
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
  return data
}

function accountFromBackend(user: { id: string; name: string; email: string; role: Role; mobile_number?: string | null; email_verified?: boolean; mobile_verified?: boolean; reminder_consent?: boolean; preferred_reminder_channel?: 'email' | 'sms' | 'both'; timezone?: string }): Account {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    mobileNumber: user.mobile_number ?? undefined,
    emailVerified: user.email_verified,
    mobileVerified: user.mobile_verified,
    reminderConsent: user.reminder_consent,
    preferredReminderChannel: user.preferred_reminder_channel,
    timezone: user.timezone,
    role: user.role,
    lastLocation: null,
  }
}

function formatCoordinates(location: LiveLocation | null) {
  if (!location) return 'Location not set'
  return `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}`
}

function locationContextFromAddress(address: Record<string, string> = {}, label = ''): LocationContext {
  return {
    label: label || [address.city || address.town || address.village || address.municipality || address.suburb, address.state, address.country].filter(Boolean).join(', ') || 'Selected map location',
    country: address.country,
    state: address.state || address.province || address.region,
    district: address.state_district || address.district || address.county,
    city: address.city || address.town || address.village || address.municipality || address.suburb,
    postcode: address.postcode,
  }
}

function mapEmbedUrl(location: LiveLocation | null) {
  if (!location) return ''
  const delta = 0.025
  const west = location.longitude - delta
  const east = location.longitude + delta
  const south = location.latitude - delta
  const north = location.latitude + delta
  return `https://www.openstreetmap.org/export/embed.html?bbox=${west}%2C${south}%2C${east}%2C${north}&layer=mapnik&marker=${location.latitude}%2C${location.longitude}`
}

function syncLocationToBackend(location: LiveLocation) {
  return apiFetch('/api/location/sync', {
    method: 'POST',
    body: JSON.stringify({ latitude: location.latitude, longitude: location.longitude, accuracy: location.accuracy, updated_at: location.updatedAt, label: location.place?.label, country: location.place?.country, state: location.place?.state, district: location.place?.district }),
  })
}

function formatValue(value: number, config: ParameterConfig) {
  return value.toFixed(config.precision)
}

function getStatus(value: number, config: ParameterConfig): Status {
  if (config.standard.direction === 'range') {
    const lower = config.standard.lower ?? config.min
    const upper = config.standard.upper ?? config.max
    if (value >= lower && value <= upper) return 'within'
    if (value >= lower - 1 && value <= upper + 1) return 'marginal'
    return 'exceeds'
  }
  if (config.standard.direction === 'high') {
    return value <= config.standard.good ? 'within' : value <= config.standard.warn ? 'marginal' : 'exceeds'
  }
  return value >= config.standard.good ? 'within' : value >= config.standard.warn ? 'marginal' : 'exceeds'
}

function classFromValues(values: Record<string, number>) {
  const pH = values.pH
  const pHIndex = 100 * Math.max(0, Math.max(6.5 - pH, pH - 8.5)) / 2
  const indices = [
    Math.max(0, pHIndex),
    100 * Math.abs(values.TDS_mg_L) / 500,
    100 * Math.abs(values.turbidity_ntu) / 5,
    100 * Math.abs(values.temperature_c - 25) / 15,
  ]
  const weights = [0.25, 0.25, 0.25, 0.25]
  const wqi = indices.reduce((total, index, position) => total + index * weights[position], 0) / weights.reduce((total, weight) => total + weight, 0)
  const label = wqi <= 25 ? 'Excellent' : wqi <= 50 ? 'Good' : wqi <= 75 ? 'Poor' : wqi <= 100 ? 'Very poor' : 'Unsuitable'
  // This client-side preview applies the documented screening formula, but it
  // is not a calibrated probability estimate from the trained artifact.
  return { label, confidence: null }
}

const navItems: { id: Page; label: string; icon: ComponentType<{ size?: number; strokeWidth?: number }> }[] = [
  { id: 'overview', label: 'Home dashboard', icon: LayoutDashboard },
  { id: 'live', label: 'Live monitoring', icon: Radio },
  { id: 'quality', label: 'Water quality', icon: Activity },
  { id: 'submit', label: 'Submit monitoring data', icon: ClipboardCheck },
  { id: 'submissions', label: 'My submissions', icon: History },
  { id: 'level', label: 'Groundwater intelligence', icon: Gauge },
  { id: 'advisor', label: 'Water advisor', icon: MessageSquare },
  { id: 'history', label: 'History & analytics', icon: RefreshCw },
  { id: 'devices', label: 'Devices & stations', icon: Zap },
  { id: 'alerts', label: 'Alerts', icon: Bell },
  { id: 'notifications', label: 'Notifications', icon: Send },
  { id: 'map', label: 'Map & locations', icon: MapPinned },
  { id: 'reports', label: 'Reports', icon: FileText },
  { id: 'education', label: 'Education & resources', icon: CircleHelp },
  { id: 'help', label: 'Help & support', icon: CircleHelp },
  { id: 'profile', label: 'User profile', icon: Users },
  { id: 'admin', label: 'Administration', icon: ShieldCheck },
]

function App({ accounts, currentAccount, onAccountUpdate, onSignOut }: { accounts: Account[]; currentAccount: Account; onAccountUpdate: (patch: Partial<Account>) => void; onSignOut: () => void }) {
  const [page, setPage] = useState<Page>('overview')
  const [values, setValues] = useState(initialValues)
  const [isLive, setIsLive] = useState(false)
  const [lastUpdated, setLastUpdated] = useState('12 sec ago')
  const [mobileNav, setMobileNav] = useState(false)
  // Dark is the product default: navy surfaces with white text. Users can still
  // switch to Bright from the account menu or Settings.
  const [theme, setTheme] = useState<Theme>(() => readStorage<Theme>('theme-v3', 'dark'))
  const [themePromptOpen, setThemePromptOpen] = useState(() => !window.localStorage.getItem(storageKey('theme-v3')))
  const [accountOpen, setAccountOpen] = useState(false)
  const [location, setLocation] = useState<LiveLocation | null>(() => currentAccount.lastLocation)
  const [trackingLocation, setTrackingLocation] = useState(false)
  const [geoStatus, setGeoStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied'>(location ? 'granted' : 'idle')
  const [updates, setUpdates] = useState<QualityUpdate[]>(() => readStorage<QualityUpdate[]>('quality-updates', []))
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null)
  const [consent, setConsent] = useState(() => readStorage<boolean | null>('privacy-consent', null))

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    writeStorage('theme-v3', theme)
  }, [theme])

  useEffect(() => {
    const checkApi = () => fetch(`${backendUrl}/api/health`).then((response) => {
      setApiStatus(response.ok ? 'online' : 'offline')
    }).catch(() => setApiStatus('offline'))
    checkApi()
    const interval = window.setInterval(checkApi, 30000)
    return () => window.clearInterval(interval)
  }, [])

  useEffect(() => {
    if (apiStatus !== 'online' || !readStorage<string | null>('api-token', null)) {
      setDashboard(null)
      return
    }
    const loadDashboard = () => apiFetch<DashboardSnapshot>('/api/dashboard').then(setDashboard).catch(() => setDashboard(null))
    loadDashboard()
    const interval = window.setInterval(loadDashboard, 30000)
    return () => window.clearInterval(interval)
  }, [apiStatus])

  useEffect(() => {
    if (!trackingLocation || !navigator.geolocation) return
    const watchId = navigator.geolocation.watchPosition((position) => {
      const nextLocation: LiveLocation = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        updatedAt: new Date().toISOString(),
      }
      setLocation(nextLocation)
      onAccountUpdate({ lastLocation: nextLocation })
      void syncLocationToBackend(nextLocation).catch(() => undefined)
      setGeoStatus('granted')
    }, () => setGeoStatus('denied'), { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 })
    return () => navigator.geolocation.clearWatch(watchId)
  }, [trackingLocation])

  const requestLocation = () => {
    setAccountOpen(false)
    if (!navigator.geolocation) {
      setGeoStatus('denied')
      return
    }
    setTrackingLocation(true)
    setGeoStatus('requesting')
    navigator.geolocation.getCurrentPosition((position) => {
      const nextLocation: LiveLocation = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        updatedAt: new Date().toISOString(),
      }
      setLocation(nextLocation)
      onAccountUpdate({ lastLocation: nextLocation })
      void syncLocationToBackend(nextLocation).catch(() => undefined)
      setGeoStatus('granted')
    }, () => setGeoStatus('denied'), { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 })
  }

  useEffect(() => {
    if (!navigator.geolocation || !navigator.permissions) return
    void navigator.permissions.query({ name: 'geolocation' }).then((permission) => {
      // Prompt once on first use; after permission is granted, keep the site
      // synchronized automatically. A denied permission remains user-controlled.
      if (permission.state !== 'denied') requestLocation()
    }).catch(() => undefined)
  }, [])

  const selectMapLocation = (nextLocation: LiveLocation) => {
    setTrackingLocation(false)
    setLocation(nextLocation)
    onAccountUpdate({ lastLocation: nextLocation })
    void syncLocationToBackend(nextLocation).catch(() => undefined)
    setGeoStatus('granted')
  }

  const submitQualityUpdate = () => {
    const update: QualityUpdate = {
      id: `${Date.now()}`,
      userName: currentAccount.name,
      role: currentAccount.role,
      values: { ...values },
      location,
      createdAt: new Date().toISOString(),
      status: 'pending',
    }
    const nextUpdates = [update, ...updates]
    setUpdates(nextUpdates)
    writeStorage('quality-updates', nextUpdates)
    setLastUpdated('sent to admin')
  }

  const reviewUpdate = (id: string) => {
    const nextUpdates = updates.map((update) => update.id === id ? { ...update, status: 'reviewed' as const } : update)
    setUpdates(nextUpdates)
    writeStorage('quality-updates', nextUpdates)
  }

  useEffect(() => {
    if (!isLive) return
    const timer = window.setInterval(() => {
      setValues((previous) => ({
        ...previous,
        pH: Math.max(6.7, Math.min(8.4, previous.pH + (Math.random() - 0.5) * 0.025)),
        EC_uS_cm: Math.max(360, Math.min(760, previous.EC_uS_cm + (Math.random() - 0.5) * 12)),
        TDS_mg_L: Math.max(200, Math.min(450, previous.TDS_mg_L + (Math.random() - 0.5) * 8)),
        Total_Hardness_mgCaCO3_L: Math.max(100, Math.min(240, previous.Total_Hardness_mgCaCO3_L + (Math.random() - 0.5) * 4)),
        Chloride_mg_L: Math.max(60, Math.min(180, previous.Chloride_mg_L + (Math.random() - 0.5) * 5)),
      }))
      setLastUpdated('just now')
    }, 4500)
    return () => window.clearInterval(timer)
  }, [isLive])

  const prediction = useMemo(() => classFromValues(values), [values])

  const navigate = (next: Page) => {
    setPage(next)
    setMobileNav(false)
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark"><Waves size={20} strokeWidth={2.3} /></div>
          <div><div className="brand-name">AquaSense AI</div><div className="brand-subtitle">Water intelligence</div></div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="site-context">
          <span className="eyebrow">Monitoring site</span>
          <button className="site-select" onClick={requestLocation}>
            <span className={`site-dot ${geoStatus === 'granted' ? '' : 'site-dot-muted'}`} />
            <span>{location ? 'Current test site' : 'Set live location'}</span><MapPinned size={14} />
          </button>
          <span className="site-coordinate">{formatCoordinates(location)}</span>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          <span className="nav-section-label">Workspace</span>
          {navItems.filter(({ id }) => id !== 'admin' || currentAccount.role === 'admin').map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => navigate(id)}><Icon size={17} /><span>{label}</span>{id === 'alerts' && <span className="nav-count">3</span>}</button>)}
          <span className="nav-section-label secondary-label">System</span>
          <button className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => navigate('settings')}><Settings size={17} /><span>Settings</span></button>
        </nav>
        <div className="sidebar-footer">
          <div className="model-chip"><span className={`status-dot ${apiStatus === 'online' ? 'green' : apiStatus === 'offline' ? 'amber' : 'cyan'}`} /><div><span className="eyebrow">Model service</span><strong>{modelProfile.version}</strong><small className="api-status-text">API {apiStatus}</small></div><Check size={15} /></div>
          <button className="user-row account-trigger" onClick={() => setAccountOpen(!accountOpen)}><div className="avatar">{currentAccount.role === 'admin' ? 'AD' : 'US'}</div><div><strong>{currentAccount.name}</strong><span>{currentAccount.role === 'admin' ? 'Administrator' : 'User'}</span></div><MoreHorizontal size={16} className="muted-icon" /></button>
        </div>
      </aside>
      {mobileNav && <button className="mobile-scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation overlay" />}
      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Monitoring</span><span className="breadcrumb-slash">/</span><strong>{navItems.find((item) => item.id === page)?.label ?? 'Settings'}</strong></div>
          <div className="topbar-actions">
            <div className="freshness"><span className={`status-dot ${location ? 'cyan' : 'amber'}`} /> {location ? 'Location linked' : 'Location needed'} <span className="freshness-time">· {lastUpdated}</span></div>
            <button className="icon-button" aria-label="Search"><Search size={17} /></button>
            <button className="icon-button notification-button" aria-label="Notifications" onClick={() => navigate('alerts')}><Bell size={17} /><span /></button>
            <button className="account-trigger top-account" onClick={() => setAccountOpen(!accountOpen)}><div className="top-avatar">{currentAccount.role === 'admin' ? 'AD' : 'US'}</div><ChevronDown size={14} /></button>
            {accountOpen && <AccountMenu account={currentAccount} theme={theme} onThemeChange={setTheme} onSignOut={onSignOut} onClose={() => setAccountOpen(false)} />}
          </div>
        </header>
        <div className="content-wrap">
          {page === 'overview' && <OverviewPage navigate={navigate} prediction={prediction} dashboard={dashboard} values={values} location={location} geoStatus={geoStatus} requestLocation={requestLocation} onSelectLocation={selectMapLocation} role={currentAccount.role} updates={updates} onReviewUpdate={reviewUpdate} accounts={accounts} />}
          {page === 'live' && <LiveMonitoringPage location={location} geoStatus={geoStatus} requestLocation={requestLocation} role={currentAccount.role} />}
          {page === 'quality' && <QualityPage values={values} setValues={setValues} prediction={prediction} isLive={isLive} setIsLive={setIsLive} location={location} role={currentAccount.role} onSubmit={submitQualityUpdate} />}
          {page === 'submit' && <SubmitMonitoringPage account={currentAccount} location={location} onSubmitted={() => setLastUpdated('submission saved')} />}
          {page === 'submissions' && <MySubmissionsPage />}
          {page === 'level' && <LevelPage />}
          {page === 'advisor' && <AdvisorPage values={values} prediction={prediction} />}
          {page === 'history' && <HistoryAnalyticsPage values={values} location={location} />}
          {page === 'devices' && <DevicesStationsPage role={currentAccount.role} location={location} />}
          {page === 'alerts' && <AlertsPage />}
          {page === 'notifications' && <NotificationsPage account={currentAccount} />}
          {page === 'map' && <MapLocationsPage location={location} geoStatus={geoStatus} requestLocation={requestLocation} onSelectLocation={selectMapLocation} accounts={accounts} />}
          {page === 'reports' && <ReportsPage />}
          {page === 'education' && <EducationPage />}
          {page === 'settings' && <SettingsPageV2 account={currentAccount} theme={theme} onThemeChange={setTheme} location={location} geoStatus={geoStatus} requestLocation={requestLocation} onSignOut={onSignOut} />}
          {page === 'help' && <HelpPage />}
          {page === 'privacy' && <PolicyPage kind="privacy" />}
          {page === 'terms' && <PolicyPage kind="terms" />}
          {page === 'profile' && <ProfilePage account={currentAccount} onAccountUpdate={onAccountUpdate} />}
          {page === 'admin' && (currentAccount.role === 'admin' ? <AdminPage accounts={accounts} /> : <AccessDeniedPage />)}
        </div>
      </main>
      {themePromptOpen && <ThemePreferenceModal onChoose={(nextTheme) => { setTheme(nextTheme); setThemePromptOpen(false) }} />}
      {consent === null && <div className="consent-banner"><strong>Privacy choices</strong><span>AquaSense uses essential storage for sign-in, theme and monitoring workflow. We do not sell customer data or use it to train AI models.</span><button className="button ghost small" onClick={() => { writeStorage('privacy-consent', false); setConsent(false) }}>Essential only</button><button className="button primary small" onClick={() => { writeStorage('privacy-consent', true); setConsent(true) }}>Accept</button><button className="text-button" onClick={() => navigate('privacy')}>Privacy policy</button></div>}
    </div>
  )
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

function OverviewPage({ navigate, prediction, dashboard, values, location, geoStatus, requestLocation, onSelectLocation, role, updates, onReviewUpdate, accounts }: { navigate: (page: Page) => void; prediction: { label: string; confidence: number | null }; dashboard: DashboardSnapshot | null; values: Record<string, number>; location: LiveLocation | null; geoStatus: 'idle' | 'requesting' | 'granted' | 'denied'; requestLocation: () => void; onSelectLocation: (location: LiveLocation) => void; role: Role; updates: QualityUpdate[]; onReviewUpdate: (id: string) => void; accounts: Account[] }) {
  const pendingUpdates = updates.filter((update) => update.status === 'pending')
  return <>
    <PageHeader eyebrow={role === 'admin' ? 'Admin · fleet overview' : 'FLEET OVERVIEW'} title={role === 'admin' ? 'Admin review center' : 'Good morning, field operator'} description={location ? `Live test site · ${formatCoordinates(location)}` : 'Set your live location to create the current test site.'} action={<button className="button primary" onClick={() => navigate('quality')}><Play size={15} /> Start quality test</button>} />
    <div className="metric-grid overview-signals">
      <MetricCard label="Live site" value={location ? 'Linked' : 'Not set'} detail={location ? 'Browser location active' : 'Permission required'} icon={<MapPinned size={17} />} tone={location ? undefined : 'amber'} />
      <MetricCard label="Admin updates" value={String(pendingUpdates.length).padStart(2, '0')} detail={role === 'admin' ? 'Pending review' : 'Sent to admin' } icon={<Bell size={17} />} tone={pendingUpdates.length ? 'amber' : undefined} />
      <MetricCard label="Quality status" value={dashboard?.latest_quality?.classification ?? 'Preview'} detail={dashboard?.latest_quality ? 'Stored approved observation' : 'Local screening only'} icon={<ShieldCheck size={17} />} />
      <MetricCard label="Profile" value={role === 'admin' ? 'Admin' : 'User'} detail="Local demo account" icon={role === 'admin' ? <ShieldCheck size={17} /> : <Radio size={17} />} />
    </div>
    <div className="overview-grid">
      <section className="panel network-panel">
        <div className="panel-heading"><div><div className="eyebrow">Live location</div><h2>Current test site</h2></div><button className="text-button" onClick={requestLocation}><MapPinned size={14} /> Update location</button></div>
        <LiveMap location={location} geoStatus={geoStatus} onRequest={requestLocation} onSelectLocation={onSelectLocation} accounts={accounts} />
        <div className="site-table"><div className="table-row table-head"><span>Site</span><span>Status</span><span>Quality</span><span>Accuracy</span></div><SiteRow name="Current test site" type={location ? formatCoordinates(location) : 'No browser location linked'} status={location ? 'Online' : 'Needs location'} quality={location ? prediction.label : 'Unavailable'} level={location ? `±${Math.round(location.accuracy)}m` : '—'} selected={!location} warning={!location} /></div>
      </section>
      <div className="right-stack">
        <section className="panel insight-card"><div className="panel-heading compact"><div><div className="eyebrow">Latest screening</div><h2>Quality insight</h2></div><Sparkles size={17} className="cyan-icon" /></div><div className="insight-verdict"><span className="quality-badge good"><span className="status-dot green" />{prediction.label}</span><span className="confidence">Confidence unavailable</span></div><p className="insight-copy">This is a four-parameter screening result based on pH, TDS, turbidity and temperature. It is not a probability estimate or potability certification.</p><div className="mini-stat-list"><MiniStat label="pH" value={values.pH.toFixed(2)} status="Within range" /><MiniStat label="Turbidity" value={`${values.turbidity_ntu.toFixed(1)} NTU`} status="Within range" /><MiniStat label="Temperature" value={`${values.temperature_c.toFixed(1)} °C`} status="Compensation value" /></div><button className="button ghost full" onClick={() => navigate('quality')}>Open quality analysis <ArrowUpRight size={14} /></button></section>
        {role === 'admin' ? <AdminUpdatePanel updates={updates} onReviewUpdate={onReviewUpdate} /> : <section className="panel alert-card"><div className="panel-heading compact"><div><div className="eyebrow">Account workflow</div><h2>Send results to admin</h2></div><ShieldCheck size={17} className="cyan-icon" /></div><AlertItem title={location ? 'Location is attached to new tests' : 'Location is required for a site'} meta={location ? 'User updates include live coordinates' : 'Use the map button above to request access'} tone={location ? 'green' : 'amber'} /><AlertItem title="Manual values are enabled" meta="Quality inputs can be edited before submission" tone="green" /></section>}
      </div>
    </div>
  </>
}

function LiveMap({ location, geoStatus, onRequest, onSelectLocation, accounts }: { location: LiveLocation | null; geoStatus: 'idle' | 'requesting' | 'granted' | 'denied'; onRequest: () => void; onSelectLocation: (location: LiveLocation) => void; accounts: Account[] }) {
  const mapNodeRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.TileLayer | null>(null)
  const markerLayerRef = useRef<L.LayerGroup | null>(null)
  const [mapLayer, setMapLayer] = useState<'street' | 'satellite' | 'terrain'>('street')
  const [selectionMode, setSelectionMode] = useState<'point' | 'area'>('point')
  const [areaStart, setAreaStart] = useState<L.LatLng | null>(null)
  const [areaBounds, setAreaBounds] = useState<L.LatLngBounds | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<LocationSearchResult[]>([])
  const [searchStatus, setSearchStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [placeContext, setPlaceContext] = useState<LocationContext | null>(() => location?.place ?? null)
  const [placeStatus, setPlaceStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>(location?.place ? 'ready' : 'idle')
  const geocodeRequestRef = useRef(0)
  const suppressAutocompleteRef = useRef(false)

  const tileConfig = {
    street: { url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors' },
    satellite: { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attribution: 'Tiles &copy; Esri' },
    terrain: { url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenTopoMap contributors' },
  }

  const reverseGeocode = async (baseLocation: LiveLocation, persist = false) => {
    const requestId = ++geocodeRequestRef.current
    setPlaceStatus('loading')
    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&zoom=18&lat=${baseLocation.latitude}&lon=${baseLocation.longitude}`, { headers: { Accept: 'application/json', 'Accept-Language': 'en' } })
      if (!response.ok) throw new Error('Reverse geocoding failed')
      const data = await response.json() as { display_name?: string; address?: Record<string, string> }
      if (requestId !== geocodeRequestRef.current) return
      const context = locationContextFromAddress(data.address, data.display_name)
      setPlaceContext(context)
      setPlaceStatus('ready')
      if (persist) onSelectLocation({ ...baseLocation, place: context })
    } catch {
      if (requestId === geocodeRequestRef.current) {
        setPlaceContext(null)
        setPlaceStatus('error')
      }
    }
  }

  const submitSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const query = searchQuery.trim()
    if (!query) return
    setSearchStatus('loading')
    setSearchResults([])
    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=5&q=${encodeURIComponent(query)}`, { headers: { Accept: 'application/json', 'Accept-Language': 'en' } })
      if (!response.ok) throw new Error('Search failed')
      const results = await response.json() as LocationSearchResult[]
      setSearchResults(results)
      setSearchStatus(results.length ? 'idle' : 'error')
    } catch {
      setSearchResults([])
      setSearchStatus('error')
    }
  }

  useEffect(() => {
    const query = searchQuery.trim()
    if (suppressAutocompleteRef.current) {
      suppressAutocompleteRef.current = false
      return
    }
    if (query.length < 3) {
      setSearchResults([])
      setSearchStatus('idle')
      return
    }
    const timer = window.setTimeout(async () => {
      setSearchStatus('loading')
      try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=5&q=${encodeURIComponent(query)}`, { headers: { Accept: 'application/json', 'Accept-Language': 'en' } })
        if (!response.ok) throw new Error('Autocomplete failed')
        const results = await response.json() as LocationSearchResult[]
        setSearchResults(results)
        setSearchStatus(results.length ? 'idle' : 'error')
      } catch {
        setSearchResults([])
        setSearchStatus('error')
      }
    }, 450)
    return () => window.clearTimeout(timer)
  }, [searchQuery])

  const selectSearchResult = (result: LocationSearchResult) => {
    const context = locationContextFromAddress(result.address, result.display_name)
    const nextLocation: LiveLocation = { latitude: Number(result.lat), longitude: Number(result.lon), accuracy: 50, updatedAt: new Date().toISOString(), place: context }
    suppressAutocompleteRef.current = true
    setSearchQuery(result.display_name)
    setSearchResults([])
    setSearchStatus('idle')
    setPlaceContext(context)
    setPlaceStatus('ready')
    setSelectionMode('point')
    setAreaStart(null)
    setAreaBounds(null)
    onSelectLocation(nextLocation)
    mapRef.current?.setView([nextLocation.latitude, nextLocation.longitude], 15, { animate: true })
  }

  const identifyArea = () => {
    if (!location || placeStatus === 'loading') return
    void reverseGeocode(location, true)
  }

  useEffect(() => {
    if (!mapNodeRef.current || mapRef.current) return
    const initial = location ? [location.latitude, location.longitude] as [number, number] : [20.5937, 78.9629] as [number, number]
    const map = L.map(mapNodeRef.current, { zoomControl: false, minZoom: 2 }).setView(initial, location ? 15 : 5)
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    const markers = L.layerGroup().addTo(map)
    mapRef.current = map
    markerLayerRef.current = markers
    return () => {
      map.remove()
      mapRef.current = null
      markerLayerRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!mapRef.current) return
    layerRef.current?.remove()
    const config = tileConfig[mapLayer]
    layerRef.current = L.tileLayer(config.url, { attribution: config.attribution, maxZoom: 19 }).addTo(mapRef.current)
  }, [mapLayer])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const handleMapClick = (event: L.LeafletMouseEvent) => {
      if (selectionMode === 'point') {
        const nextLocation: LiveLocation = { latitude: event.latlng.lat, longitude: event.latlng.lng, accuracy: 5, updatedAt: new Date().toISOString() }
        setPlaceContext(null)
        setPlaceStatus('idle')
        onSelectLocation(nextLocation)
        return
      }
      if (!areaStart) {
        setAreaStart(event.latlng)
        return
      }
      const bounds = L.latLngBounds(areaStart, event.latlng)
      setAreaBounds(bounds)
      const center = bounds.getCenter()
      const northSouthMeters = Math.abs(bounds.getNorth() - bounds.getSouth()) * 111000
      const eastWestMeters = Math.abs(bounds.getEast() - bounds.getWest()) * 111000 * Math.cos(center.lat * Math.PI / 180)
      const nextLocation: LiveLocation = { latitude: center.lat, longitude: center.lng, accuracy: Math.max(10, Math.round(Math.max(northSouthMeters, eastWestMeters) / 2)), updatedAt: new Date().toISOString() }
      setPlaceContext(null)
      setPlaceStatus('idle')
      onSelectLocation(nextLocation)
      setAreaStart(null)
    }
    map.on('click', handleMapClick)
    return () => { map.off('click', handleMapClick) }
  }, [selectionMode, areaStart, onSelectLocation])

  useEffect(() => {
    if (!mapRef.current || !location) return
    mapRef.current.setView([location.latitude, location.longitude], Math.max(mapRef.current.getZoom(), 15), { animate: true })
  }, [location?.latitude, location?.longitude])

  useEffect(() => {
    if (location && !location.place) void reverseGeocode(location)
  }, [location?.latitude, location?.longitude, location?.updatedAt])

  useEffect(() => {
    const markers = markerLayerRef.current
    if (!markers) return
    markers.clearLayers()
    if (location) {
      L.circleMarker([location.latitude, location.longitude], { radius: 9, color: '#111111', weight: 3, fillColor: '#ffffff', fillOpacity: 1 }).bindPopup('<b>Current test site</b><br/>Live browser location').addTo(markers)
    }
    accounts.filter((account) => account.lastLocation).forEach((account) => {
      const accountLocation = account.lastLocation as LiveLocation
      L.circleMarker([accountLocation.latitude, accountLocation.longitude], { radius: account.role === 'admin' ? 7 : 6, color: '#222222', weight: 2, fillColor: account.role === 'admin' ? '#ffffff' : '#888888', fillOpacity: .9 }).bindPopup(`<b>${account.name}</b><br/>${account.role === 'admin' ? 'Admin' : 'User'} · active account`).addTo(markers)
    })
    if (areaBounds) L.rectangle(areaBounds, { color: '#444444', weight: 2, fillColor: '#999999', fillOpacity: .12 }).addTo(markers)
  }, [location, accounts, areaBounds])

  const nearbyUsers = accounts.filter((account) => account.lastLocation).length
  const placeTitle = placeContext ? [placeContext.city, placeContext.district, placeContext.state].filter(Boolean).slice(0, 2).join(', ') || placeContext.country || 'Selected site' : placeStatus === 'loading' ? 'Resolving area name…' : location ? 'Selected map site' : 'No site selected'
  return <div className="map-panel live-map-shell">
    <div className="map-search-wrap">
      <form className="map-search-form" onSubmit={submitSearch}>
        <Search size={15} />
        <input aria-label="Search map location" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search city, village, address…" />
        <button type="submit">{searchStatus === 'loading' ? 'Searching…' : 'Search'}</button>
      </form>
      {searchStatus === 'error' && <div className="map-search-message">No matching place found. Try a city, village, district, or full address.</div>}
      {searchResults.length > 0 && <div className="map-search-results">{searchResults.map((result) => <button type="button" key={result.place_id} onClick={() => selectSearchResult(result)}><MapPin size={14} /><span><strong>{result.display_name.split(',')[0]}</strong><small>{result.display_name}</small></span></button>)}</div>}
    </div>
    <div className="map-canvas">
      <div ref={mapNodeRef} className="leaflet-map" />
      <div className="map-toolbar"><div className="map-layer-buttons"><button className={mapLayer === 'street' ? 'selected' : ''} onClick={() => setMapLayer('street')}>Street</button><button className={mapLayer === 'satellite' ? 'selected' : ''} onClick={() => setMapLayer('satellite')}>Satellite</button><button className={mapLayer === 'terrain' ? 'selected' : ''} onClick={() => setMapLayer('terrain')}>Terrain</button></div><div className="map-select-buttons"><button className={selectionMode === 'point' ? 'selected' : ''} onClick={() => { setSelectionMode('point'); setAreaStart(null) }}><Crosshair size={13} /> Point</button><button className={selectionMode === 'area' ? 'selected' : ''} onClick={() => setSelectionMode('area')}><Layers3 size={13} /> Area</button></div></div>
      <div className="map-live-badge"><span className={`status-dot ${location ? 'cyan' : 'amber'}`} />{location ? `Site · ±${Math.round(location.accuracy)}m` : 'Map ready · click to select'}</div>
      <div className="map-user-count"><Users size={13} /> {nearbyUsers} account{nearbyUsers === 1 ? '' : 's'} mapped</div>
      <div className="map-location-actions"><button className="map-control-button" onClick={onRequest} aria-label="Use current location"><LocateFixed size={15} />{geoStatus === 'requesting' ? 'Locating…' : 'My location'}</button>{selectionMode === 'area' && <span>{areaStart ? 'Click the second corner' : 'Click two corners'}</span>}</div>
    </div>
    <div className="map-context-panel">
      <div className="map-context-header"><div className="map-context-title"><MapPinned size={16} /><div><strong>{placeTitle}</strong><span>{placeContext?.label ?? (location ? formatCoordinates(location) : 'Search or click the map to set a site')}</span></div></div><div className="map-context-actions">{location && !placeContext && <button className="map-identify-button" onClick={identifyArea} disabled={placeStatus === 'loading'}><MapPinned size={12} />{placeStatus === 'loading' ? 'Resolving…' : 'Identify area'}</button>}<span className={`map-context-status ${placeStatus}`}>{placeStatus === 'loading' ? 'Resolving…' : placeStatus === 'error' ? 'Name unavailable' : placeContext ? 'Area identified' : 'Waiting for site'}</span></div></div>
      <div className="map-context-grid"><div><span>COUNTRY</span><strong>{placeContext?.country ?? '—'}</strong></div><div><span>STATE / PROVINCE</span><strong>{placeContext?.state ?? '—'}</strong></div><div><span>DISTRICT / COUNTY</span><strong>{placeContext?.district ?? '—'}</strong></div><div><span>CITY / TOWN</span><strong>{placeContext?.city ?? '—'}</strong></div></div>
      <div className="map-context-footer"><span>{location ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}` : 'No coordinates selected'}</span><span>Area names via OpenStreetMap</span></div>
    </div>
  </div>
}

function AdminUpdatePanel({ updates, onReviewUpdate }: { updates: QualityUpdate[]; onReviewUpdate: (id: string) => void }) {
  const pending = updates.filter((update) => update.status === 'pending')
  return <section className="panel alert-card admin-update-card"><div className="panel-heading compact"><div><div className="eyebrow">Admin inbox</div><h2>User quality updates</h2></div><span className="quality-badge amber"><span className="status-dot amber" />{pending.length} pending</span></div>{pending.length === 0 ? <div className="empty-state"><Check size={16} className="green-icon" />No pending user submissions.</div> : pending.slice(0, 3).map((update) => <div className="admin-update" key={update.id}><div className="update-avatar">FO</div><div className="update-copy"><strong>{update.userName}</strong><span>{update.location ? formatCoordinates(update.location) : 'No location attached'} · {new Date(update.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></div><button className="button ghost small" onClick={() => onReviewUpdate(update.id)}><Check size={13} /> Review</button></div>)}</section>
}

function AccountMenu({ account, theme, onThemeChange, onSignOut, onClose }: { account: Account; theme: Theme; onThemeChange: (theme: Theme) => void; onSignOut: () => void; onClose: () => void }) {
  return <div className="account-popover"><div className="account-popover-head"><div className="avatar">{account.role === 'admin' ? 'AD' : 'US'}</div><div><strong>{account.name}</strong><span>{account.role === 'admin' ? 'Admin account' : 'User account'}</span></div></div><div className="account-role-note"><ShieldCheck size={14} />{account.role === 'admin' ? 'You own this monitoring workspace.' : 'Your readings and location go to the admin.'}</div><div className="popover-label">BACKGROUND</div><div className="theme-switch"><button className={theme === 'light' ? 'selected' : ''} onClick={() => onThemeChange('light')}><Sun size={14} />Bright</button><button className={theme === 'dark' ? 'selected' : ''} onClick={() => onThemeChange('dark')}><Moon size={14} />Dark</button></div><button className="sign-out-button" onClick={onSignOut}><LogOut size={14} /> Sign out</button><button className="popover-close" onClick={onClose}>Close account menu</button></div>
}

function ThemePreferenceModal({ onChoose }: { onChoose: (theme: Theme) => void }) {
  return <div className="modal-scrim"><section className="theme-modal" role="dialog" aria-modal="true" aria-labelledby="theme-title"><div className="theme-modal-icon"><Sun size={19} /></div><div className="eyebrow">First-time setup</div><h2 id="theme-title">Choose your workspace background</h2><p>Pick a bright or dark surface. You can change this later from your account menu.</p><div className="theme-choice-grid"><button onClick={() => onChoose('light')} className="theme-choice bright"><span className="theme-preview light-preview" /><strong>Bright</strong><span>High visibility in daylight</span></button><button onClick={() => onChoose('dark')} className="theme-choice dark"><span className="theme-preview dark-preview" /><strong>Dark</strong><span>Low-light operations</span></button></div></section></div>
}

function QualityPage({ values, setValues, prediction, isLive, setIsLive, location, role, onSubmit }: { values: Record<string, number>; setValues: React.Dispatch<React.SetStateAction<Record<string, number>>>; prediction: { label: string; confidence: number | null }; isLive: boolean; setIsLive: (value: boolean) => void; location: LiveLocation | null; role: Role; onSubmit: () => void }) {
  const [captured, setCaptured] = useState(false)
  return <>
    <PageHeader eyebrow="Water quality · live" title="Live quality analysis" description={location ? `Current test site · ${formatCoordinates(location)}` : 'No live location linked · set location from the overview map'} action={<div className="session-actions"><div className={`stream-state ${isLive ? 'is-live' : ''}`}><span className={`status-dot ${isLive ? 'cyan' : 'amber'}`} />{isLive ? 'Streaming' : 'Manual input'}</div><button className="button primary" onClick={() => { setCaptured(true); setIsLive(false) }}><RefreshCw size={15} /> Capture reading</button></div>} />
    <div className="quality-layout">
      <section className="panel sensor-panel"><div className="panel-heading"><div><div className="eyebrow">Quality inputs</div><h2>Current parameters</h2></div><button className="icon-button" onClick={() => setIsLive(!isLive)} aria-label={isLive ? 'Pause stream' : 'Resume stream'}>{isLive ? <span className="pause-icon">Ⅱ</span> : <Play size={16} />}</button></div><div className="stabilization"><span className={`status-dot ${captured ? 'green' : 'amber'}`} /><div><strong>{captured ? 'Reading captured' : 'Manual values ready'}</strong><span>{captured ? 'Values are ready to send to the admin account' : 'Enter calibrated sensor values, then capture the reading'}</span></div><Check size={16} /></div><div className="parameter-grid">{parameterConfig.map((config) => <ParameterTile key={config.key} config={config} value={values[config.key]} onChange={(next) => setValues((previous) => ({ ...previous, [config.key]: next }))} />)}</div><div className="sensor-footer"><div><span className="eyebrow">Site location</span><strong>{location ? formatCoordinates(location) : 'Not linked'}</strong></div><div><span className="eyebrow">Input mode</span><strong className="signal-good">Manual</strong></div><div><span className="eyebrow">Role</span><strong>{role === 'admin' ? 'Admin' : 'User'}</strong></div></div></section>
      <section className="panel prediction-panel"><div className="panel-heading"><div><div className="eyebrow">Screening method</div><h2>Quality classification</h2></div><span className="model-label">{modelProfile.version}</span></div><div className="prediction-ring"><div className="ring-track" /><div className="ring-progress" style={{ '--confidence': '0deg' } as React.CSSProperties} /><div className="ring-content"><strong>—</strong><span>confidence not calibrated</span></div></div><div className="prediction-label"><span className="status-dot green" /><strong>{prediction.label}</strong><span>Four-parameter screening: pH, TDS, turbidity and temperature</span></div><div className="prediction-divider" /><div className="parameter-statuses">{parameterConfig.map((config) => <div className="status-line" key={config.key}><span>{config.short}</span><span className={`status-pill ${getStatus(values[config.key], config)}`}>{getStatus(values[config.key], config) === 'within' ? 'Within' : getStatus(values[config.key], config) === 'marginal' ? 'Marginal' : 'Exceeds'}</span></div>)}</div><div className="contract-note"><CircleHelp size={15} /><span>Inference contract validates pH, TDS, turbidity and temperature order, units, and ranges before prediction.</span></div></section>
      <InsightPanel prediction={prediction} values={values} role={role} location={location} onSubmit={onSubmit} />
    </div>
    <div className="honesty-banner"><ShieldCheck size={17} /><div><strong>Screening boundary</strong><span>This result uses pH, TDS, turbidity and temperature only. Bacteriological, nitrate, fluoride, hardness and heavy-metal parameters are not measured. Laboratory analysis is required for health-critical decisions.</span></div><button className="text-button">Read limitations <ArrowUpRight size={14} /></button></div>
  </>
}

function ParameterTile({ config, value, onChange }: { config: ParameterConfig; value: number; onChange: (value: number) => void }) {
  const Icon = config.icon
  const status = getStatus(value, config)
  const percent = Math.min(100, Math.max(8, (value / config.max) * 100))
  return <div className={`parameter-tile ${status}`}><div className="tile-top"><div className="tile-icon" style={{ color: config.color, background: `${config.color}16` }}><Icon size={16} /></div><span className={`status-dot ${status === 'within' ? 'green' : status === 'marginal' ? 'amber' : 'red'}`} /></div><div className="tile-name">{config.name}</div><div className="tile-value-row"><input className="parameter-input" aria-label={`${config.name} value`} type="number" min={config.min} max={config.max} step={config.precision === 0 ? 1 : 0.01} value={value} onChange={(event) => onChange(Number(event.target.value))} /><span>{config.unit}</span></div><div className="sparkline"><span style={{ width: `${percent}%`, background: config.color }} /><i /><i /><i /><i /><i /></div><div className="tile-range"><span>Valid {config.min}–{config.max}</span><span className="manual-label">Manual entry</span></div></div>
}

function InsightPanel({ prediction, values, role, location, onSubmit }: { prediction: { label: string; confidence: number | null }; values: Record<string, number>; role: Role; location: LiveLocation | null; onSubmit: () => void }) {
  return <section className="panel insight-panel"><div className="panel-heading"><div><div className="eyebrow">Evidence note</div><h2>Interpretation</h2></div><span className="generated-label"><Sparkles size={13} /> Local method</span></div><div className="insight-section"><span className="insight-label">VERDICT</span><p className="verdict-text">{prediction.label} screening classification. Confidence is not reported because this browser calculation is not a calibrated probability estimate.</p></div><div className="insight-section"><span className="insight-label">KEY FINDINGS</span><div className="finding-list"><Finding label="pH" value={values.pH.toFixed(2)} limit="6.5–8.5" /><Finding label="TDS" value={`${Math.round(values.TDS_mg_L)} mg/L`} limit="500 mg/L" /><Finding label="Turbidity" value={`${values.turbidity_ntu.toFixed(1)} NTU`} limit="5 NTU" /><Finding label="Temperature" value={`${values.temperature_c.toFixed(1)} °C`} limit="15°C deviation" /></div></div><div className="insight-section"><span className="insight-label">SUITABILITY</span><div className="suitability-grid"><Suitability label="Drinking" state="Conditional" tone="amber" /><Suitability label="Irrigation" state="Likely suitable" tone="green" /><Suitability label="Domestic" state="Likely suitable" tone="green" /></div></div><div className="insight-section"><span className="insight-label">LIMITATIONS</span><p className="limitation-text">Sensor-based screening from pH, TDS, turbidity and temperature, not a certification of potability. Bacteriological, nitrate, fluoride, hardness and heavy-metal parameters were not measured. Laboratory analysis is required for health-critical decisions.</p></div><button className="button ghost full" onClick={onSubmit} disabled={!location}>{role === 'admin' ? 'Save admin reading' : 'Send reading and location to admin'} <ArrowUpRight size={14} /></button>{!location && <p className="submit-hint"><MapPinned size={13} /> Set live location before submitting this result.</p>}</section>
}

function Finding({ label, value, limit }: { label: string; value: string; limit: string }) { return <div className="finding"><span className="status-dot green" /><div><strong>{label}</strong><span>{value} <em>· limit {limit}</em></span></div><Check size={14} className="green-icon" /></div> }
function Suitability({ label, state, tone }: { label: string; state: string; tone: string }) { return <div className="suitability"><span>{label}</span><strong className={tone}>{state}</strong></div> }

function LevelPage() {
  return <><div className="demo-banner"><CircleHelp size={15} /><span><strong>Preview series</strong> The level chart below is illustrative until an approved groundwater time series is loaded from the backend.</span></div><PageHeader eyebrow="Groundwater · level" title="Groundwater level" description="Civic Tank 04 · Level sensor LS-018" action={<button className="button ghost"><SlidersHorizontal size={15} /> Calibration</button>} /><div className="level-grid"><section className="panel gauge-panel"><div className="panel-heading"><div><div className="eyebrow">Current level</div><h2>Storage status</h2></div><span className="quality-badge amber"><span className="status-dot amber" />Preview</span></div><div className="gauge-wrap"><div className="gauge-outer"><div className="gauge-inner"><strong>—</strong><small>awaiting data</small></div><div className="gauge-fill" /></div><div className="gauge-scale"><span>0%</span><span>50%</span><span>100%</span></div></div><div className="gauge-details"><div><span className="eyebrow">Depth to water</span><strong>—</strong></div><div><span className="eyebrow">Rate of change</span><strong>—</strong></div><div><span className="eyebrow">Projected critical</span><strong>—</strong></div></div></section><section className="panel chart-panel"><div className="panel-heading"><div><div className="eyebrow">Level trend</div><h2>No approved series loaded</h2></div><span className="model-label">Awaiting backend data</span></div><div className="empty-module"><Gauge size={22} className="cyan-icon" /><p>Import or ingest groundwater observations to render a hydrograph and forecast.</p></div></section></div><div className="metric-grid level-metrics"><MetricCard label="7-day trend" value="—" detail="Requires stored observations" icon={<ArrowDownRight size={17} />} /><MetricCard label="30-day average" value="—" detail="Requires stored observations" icon={<Activity size={17} />} /><MetricCard label="Threshold" value="Configured" detail="Review alert rules in settings" icon={<AlertTriangle size={17} />} /></div><div className="honesty-banner"><Gauge size={17} /><div><strong>Sensor calibration</strong><span>Calibration age is shown when a registered device reports its calibration metadata.</span></div><button className="text-button">Open calibration <ArrowUpRight size={14} /></button></div></>
}

function AlertsPage() {
  const [alerts, setAlerts] = useState<Array<{ id: string; title: string; detail: string; severity: string; state: string; created_at: string }>>([])
  const load = () => apiFetch<typeof alerts>('/api/alerts').then(setAlerts).catch(() => fetch(`${backendUrl}/api/alerts/live-preview`).then((response) => response.ok ? response.json() as Promise<typeof alerts> : Promise.reject()).then(setAlerts).catch(() => setAlerts([])))
  useEffect(() => { load() }, [])
  return <><div className="demo-banner"><Bell size={15} /><span><strong>{alerts.length ? 'Live admin notifications' : 'No active notifications'}</strong> Device review, promotion, and data-quality events are stored in the backend alert center.</span></div><PageHeader eyebrow="Operations · alerts" title="Alerts" description="Review active conditions across your monitoring network." action={<button className="button ghost" onClick={load}><RefreshCw size={14} /> Refresh alerts</button>} /><section className="panel alerts-table"><div className="table-row table-head"><span>Alert</span><span>Detail</span><span>Triggered</span><span>Severity</span><span>State</span><span /></div>{alerts.length === 0 ? <div className="empty-module"><CheckCircle2 size={24} className="cyan-icon" /><h2>Alert center is clear</h2><p>New device readings waiting for review will notify the administrator here.</p></div> : alerts.map((alert) => <div className="table-row" key={alert.id}><span className="alert-title"><span className={`alert-icon ${alert.severity === 'critical' ? 'red' : alert.severity === 'warning' ? 'amber' : 'green'}`}><Bell size={13} /></span><strong>{alert.title}</strong></span><span>{alert.detail}</span><span className="muted-cell">{new Date(alert.created_at).toLocaleString()}</span><span><span className={`severity ${alert.severity}`}>{alert.severity}</span></span><span><span className={`state ${alert.state}`}>{alert.state}</span></span><span /></div>)}</section></>
}
function ReportsPage() { return <><div className="demo-banner"><CircleHelp size={15} /><span><strong>Report workspace</strong> Report rows populate from selected stored observations. Preview rows are not downloadable measurements.</span></div><PageHeader eyebrow="Documents · reports" title="Reports and exports" description="Generated screening reports and machine-readable data exports." action={<button className="button primary"><FileText size={15} /> Generate report</button>} /><div className="report-summary"><MetricCard label="Reports this month" value="—" detail="No stored report metadata" icon={<FileText size={17} />} /><MetricCard label="Readings exported" value="—" detail="Choose a station and period" icon={<Cloud size={17} />} /><MetricCard label="Last report" value="—" detail="No report generated" icon={<Check size={17} />} /></div><section className="panel reports-table"><div className="panel-heading"><div><div className="eyebrow">Recent reports</div><h2>Generated documents</h2></div><button className="text-button">Export CSV <ArrowUpRight size={14} /></button></div><div className="empty-module"><FileText size={22} className="cyan-icon" /><p>Generate a report after selecting approved data from the backend.</p></div></section></> }
 function SettingsPage({ role, onRoleChange, theme, onThemeChange, location, geoStatus, requestLocation }: { role: Role; onRoleChange: (role: Role) => void; theme: Theme; onThemeChange: (theme: Theme) => void; location: LiveLocation | null; geoStatus: 'idle' | 'requesting' | 'granted' | 'denied'; requestLocation: () => void }) { return <><PageHeader eyebrow="System · settings" title="Settings" description="Configure account access, location sharing, and model defaults." /><section className="panel account-settings-card"><div className="panel-heading"><div><div className="eyebrow">Account and location</div><h2>Sharing controls</h2></div><span className="quality-badge good"><span className="status-dot green" />{role === 'admin' ? 'Admin' : 'User'}</span></div><div className="account-settings-grid"><div><span className="eyebrow">Role</span><div className="role-switch inline"><button className={role === 'user' ? 'selected' : ''} onClick={() => onRoleChange('user')}><Radio size={14} />User</button><button className={role === 'admin' ? 'selected' : ''} onClick={() => onRoleChange('admin')}><ShieldCheck size={14} />Admin</button></div></div><div><span className="eyebrow">Background</span><div className="theme-switch inline"><button className={theme === 'light' ? 'selected' : ''} onClick={() => onThemeChange('light')}><Sun size={14} />Bright</button><button className={theme === 'dark' ? 'selected' : ''} onClick={() => onThemeChange('dark')}><Moon size={14} />Dark</button></div></div><div><span className="eyebrow">Live site location</span><strong className="setting-location">{location ? formatCoordinates(location) : 'Not connected'}</strong><button className="text-button" onClick={requestLocation}><MapPinned size={14} /> {geoStatus === 'requesting' ? 'Requesting' : 'Use current location'}</button></div></div><div className="setting-note"><MapPinned size={15} />User submissions include the current browser location so an admin can review where the test was performed.</div></section><div className="settings-grid"><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Model information</div><h2>Inference contract</h2></div><span className="quality-badge good"><span className="status-dot green" />Trained profile</span></div><div className="setting-row"><span>Model version</span><strong>{modelProfile.version}</strong></div><div className="setting-row"><span>Expected features</span><strong>{modelProfile.featureOrder.length} parameters</strong></div><div className="setting-row"><span>Feature order</span><strong className="mono">{modelProfile.featureOrder.join(' → ')}</strong></div><div className="setting-row"><span>Output labels</span><strong>{modelProfile.classes.join(' · ')}</strong></div><div className="setting-note"><CircleHelp size={15} />{modelProfile.source}. The labels are derived from a screening formula, not laboratory-confirmed classes.</div></section><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Quality parameters</div><h2>Configured inputs</h2></div><button className="icon-button"><MoreHorizontal size={17} /></button></div>{parameterConfig.map((config) => <div className="setting-row" key={config.key}><span><span className="setting-name-dot" style={{ background: config.color }} />{config.name}</span><strong>{config.unit} · valid {config.min}–{config.max}</strong></div>)}<div className="setting-note"><SlidersHorizontal size={15} />Parameter configuration drives tiles, validation, feature vectors, and report tables.</div></section><section className="panel settings-panel wide"><div className="panel-heading"><div><div className="eyebrow">Reference standards</div><h2>Screening limits</h2></div><button className="button ghost small">Edit limits</button></div><p className="settings-copy">Current reference: configurable BIS IS 10500 profile. Verify limits against the current standard before making health-critical decisions.</p><div className="standards-table"><div className="table-row table-head"><span>Parameter</span><span>Unit</span><span>Good range</span><span>Review above</span></div>{parameterConfig.map((config) => <div className="table-row" key={config.key}><span>{config.name}</span><span className="muted-cell">{config.unit}</span><span className="mono">≤ {config.standard.good}</span><span className="mono">&gt; {config.standard.warn}</span></div>)}</div></section></div></> }

function SettingsPageV2({ account, theme, onThemeChange, location, geoStatus, requestLocation, onSignOut }: { account: Account; theme: Theme; onThemeChange: (theme: Theme) => void; location: LiveLocation | null; geoStatus: 'idle' | 'requesting' | 'granted' | 'denied'; requestLocation: () => void; onSignOut: () => void }) {
  return <><PageHeader eyebrow="System · settings" title="Settings" description="Configure account access, location sharing, and model defaults." /><section className="panel account-settings-card"><div className="panel-heading"><div><div className="eyebrow">Account and location</div><h2>Sharing controls</h2></div><span className="quality-badge good"><span className="status-dot green" />{account.role === 'admin' ? 'Admin' : 'User'}</span></div><div className="account-settings-grid"><div><span className="eyebrow">Account</span><strong className="setting-location">{account.name}</strong><span className="muted-cell">{account.email}</span></div><div><span className="eyebrow">Background</span><div className="theme-switch inline"><button className={theme === 'light' ? 'selected' : ''} onClick={() => onThemeChange('light')}><Sun size={14} />Bright</button><button className={theme === 'dark' ? 'selected' : ''} onClick={() => onThemeChange('dark')}><Moon size={14} />Dark</button></div></div><div><span className="eyebrow">Live site location</span><strong className="setting-location">{location ? formatCoordinates(location) : 'Not connected'}</strong><button className="text-button" onClick={requestLocation}><MapPinned size={14} /> {geoStatus === 'requesting' ? 'Requesting' : 'Use current location'}</button></div></div><div className="setting-note"><MapPinned size={15} />User submissions include the current browser location so an admin can review where the test was performed.</div><button className="button ghost small settings-signout" onClick={onSignOut}><LogOut size={14} /> Sign out</button></section><div className="settings-grid"><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Model information</div><h2>Inference contract</h2></div><span className="quality-badge good"><span className="status-dot green" />Trained profile</span></div><div className="setting-row"><span>Model version</span><strong>{modelProfile.version}</strong></div><div className="setting-row"><span>Expected features</span><strong>{modelProfile.featureOrder.length} parameters</strong></div><div className="setting-row"><span>Feature order</span><strong className="mono">{modelProfile.featureOrder.join(' → ')}</strong></div><div className="setting-row"><span>Output labels</span><strong>{modelProfile.classes.join(' · ')}</strong></div><div className="setting-note"><CircleHelp size={15} />{modelProfile.source}. The labels are derived from a screening formula, not laboratory-confirmed classes.</div></section><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Quality parameters</div><h2>Configured inputs</h2></div><button className="icon-button"><MoreHorizontal size={17} /></button></div>{parameterConfig.map((config) => <div className="setting-row" key={config.key}><span><span className="setting-name-dot" style={{ background: config.color }} />{config.name}</span><strong>{config.unit} · valid {config.min}–{config.max}</strong></div>)}<div className="setting-note"><SlidersHorizontal size={15} />Parameter configuration drives tiles, validation, feature vectors, and report tables.</div></section><section className="panel settings-panel wide"><div className="panel-heading"><div><div className="eyebrow">Reference standards</div><h2>Screening limits</h2></div><button className="button ghost small">Edit limits</button></div><p className="settings-copy">Current reference: configurable BIS IS 10500 profile. Verify limits against the current standard before making health-critical decisions.</p><div className="standards-table"><div className="table-row table-head"><span>Parameter</span><span>Unit</span><span>Good range</span><span>Review above</span></div>{parameterConfig.map((config) => <div className="table-row" key={config.key}><span>{config.name}</span><span className="muted-cell">{config.unit}</span><span className="mono">≤ {config.standard.good}</span><span className="mono">&gt; {config.standard.warn}</span></div>)}</div></section></div></>
}

type StationOption = { id: string; name: string; state?: string | null; district?: string | null }
type SubmissionRecord = { id: string; station_id: string; device_id?: string | null; measurement_at: string; submitted_at?: string | null; status: string; source: string; measurement_method: string; remarks?: string | null; groundwater?: Record<string, unknown> | null; quality?: Record<string, unknown> | null; validation_warnings: { severity: string; detail: string }[]; review_feedback?: string | null; version: number }
type DeviceReviewRecord = { id: string; device_id: string; timestamp: string; distance_cm?: number | null; water_level_percent?: number | null; water_depth_cm?: number | null; quality_status: string; station_id?: string | null; site_latitude?: number | null; site_longitude?: number | null }

function SubmitMonitoringPage({ account, location, onSubmitted }: { account: Account; location: LiveLocation | null; onSubmitted: () => void }) {
  const [stations, setStations] = useState<StationOption[]>([])
  const [stationId, setStationId] = useState('')
  const [category, setCategory] = useState<'quality' | 'groundwater'>('quality')
  const [measurementAt, setMeasurementAt] = useState(() => new Date().toISOString().slice(0, 16))
  const [method, setMethod] = useState('manual')
  const [remarks, setRemarks] = useState('')
  const [quality, setQuality] = useState<Record<string, string>>({ ph: '7.34', tds_mg_l: '284', ec_us_cm: '486', turbidity_ntu: '', temperature_c: '', hardness_mg_l: '168', chloride_mg_l: '92' })
  const [groundwater, setGroundwater] = useState<Record<string, string>>({ groundwater_level_m: '', distance_cm: '', water_depth_cm: '', water_level_percent: '', rainfall_mm: '' })
  const [attachment, setAttachment] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch<StationOption[]>('/api/stations').then((items) => { setStations(items); if (items[0]) setStationId(items[0].id) }).catch(() => {
      const localStation = { id: 'local-current-site', name: location ? `Current site · ${formatCoordinates(location)}` : 'Current test site' }
      setStations([localStation])
      setStationId(localStation.id)
    })
  }, [location])

  const numberOrUndefined = (value: string) => value.trim() === '' ? undefined : Number(value)
  const submit = async (saveAsDraft: boolean) => {
    setBusy(true); setError(''); setMessage('')
    try {
      if (!stationId) throw new Error('Select a monitoring station before saving the submission.')
      const groundwaterPayload = category === 'groundwater' ? Object.fromEntries(Object.entries(groundwater).map(([key, value]) => [key, numberOrUndefined(value)]).filter(([, value]) => value !== undefined)) : undefined
      const qualityPayload = category === 'quality' ? Object.fromEntries(Object.entries(quality).map(([key, value]) => [key, numberOrUndefined(value)]).filter(([, value]) => value !== undefined)) : undefined
      if (!groundwaterPayload && !qualityPayload) throw new Error('Enter at least one measured value.')
      const payload = { station_id: stationId, measurement_at: new Date(measurementAt).toISOString(), measurement_method: method, source: 'user-entered', groundwater: groundwaterPayload, quality: qualityPayload, remarks: remarks.trim() || undefined, save_as_draft: saveAsDraft }
      let created: SubmissionRecord
      try {
        created = await apiFetch<SubmissionRecord>('/api/submissions', { method: 'POST', body: JSON.stringify(payload) })
      } catch (apiError) {
        if (!readStorage<string | null>('api-token', null)) {
          const localItems = readStorage<SubmissionRecord[]>('local-submissions', [])
          created = { id: `local-${Date.now()}`, station_id: stationId, measurement_at: payload.measurement_at, status: saveAsDraft ? 'Draft' : 'Submitted', source: 'user-entered', measurement_method: method, remarks, validation_warnings: [], version: 1, quality: qualityPayload, groundwater: groundwaterPayload }
          writeStorage('local-submissions', [created, ...localItems])
        } else throw apiError
      }
      if (attachment && created.id && !created.id.startsWith('local-')) {
        const token = readStorage<string | null>('api-token', null)
        const form = new FormData(); form.append('file', attachment)
        const response = await fetch(`${backendUrl}/api/submissions/${created.id}/attachments`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : undefined, body: form })
        if (!response.ok) throw new Error('Submission saved, but the attachment could not be stored.')
      }
      setMessage(saveAsDraft ? 'Draft saved. You can return to My submissions and continue it.' : 'Submission received. It is awaiting administrator review before analytics use.')
      onSubmitted()
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save submission.')
    } finally { setBusy(false) }
  }

  const updateField = (setter: React.Dispatch<React.SetStateAction<Record<string, string>>>, key: string, value: string) => setter((previous) => ({ ...previous, [key]: value }))
  return <><PageHeader eyebrow="Data submission · weekly" title="Submit monitoring data" description={`Create an auditable water observation for ${account.name}. Unreviewed records never enter approved analytics.`} action={<span className="quality-badge good"><CheckCircle2 size={14} /> Central record</span>} />
    <section className="submission-workflow"><div className="submission-step active"><span>1</span><div><strong>Enter</strong><small>Validated values</small></div></div><div className="submission-step"><span>2</span><div><strong>Review</strong><small>Administrator queue</small></div></div><div className="submission-step"><span>3</span><div><strong>Approve</strong><small>Analytics eligible</small></div></div></section>
    <section className="panel submission-panel"><div className="panel-heading"><div><div className="eyebrow">Observation context</div><h2>Where and when was this measured?</h2></div><span className="model-label">Original values preserved</span></div><div className="form-grid three"><label>Monitoring station<select value={stationId} onChange={(event) => setStationId(event.target.value)}><option value="">Select station</option>{stations.map((station) => <option value={station.id} key={station.id}>{station.name}{station.state ? ` · ${station.state}` : ''}</option>)}</select></label><label>Measurement timestamp<input type="datetime-local" value={measurementAt} onChange={(event) => setMeasurementAt(event.target.value)} /></label><label>Measurement method<select value={method} onChange={(event) => setMethod(event.target.value)}><option value="manual">Manual sensor entry</option><option value="device">Registered device</option><option value="laboratory">Laboratory result</option><option value="imported">Imported historical data</option></select></label></div><div className="submission-location-note"><MapPinned size={15} /><span>{location ? `Current site context linked at ${formatCoordinates(location)}. Select the matching registered station above.` : 'No browser location is linked. Choose a registered monitoring station.'}</span></div></section>
    <section className="panel submission-panel"><div className="panel-heading"><div><div className="eyebrow">Measurement category</div><h2>Choose what you are submitting</h2></div><div className="segmented-control"><button className={category === 'quality' ? 'selected' : ''} onClick={() => setCategory('quality')}><Droplets size={14} />Water quality</button><button className={category === 'groundwater' ? 'selected' : ''} onClick={() => setCategory('groundwater')}><Gauge size={14} />Groundwater</button></div></div>{category === 'quality' ? <div className="form-grid three submission-fields"><Field label="pH" unit="pH" value={quality.ph} onChange={(value) => updateField(setQuality, 'ph', value)} min="0" max="14" step="0.01" /><Field label="Total Dissolved Solids (TDS)" unit="mg/L" value={quality.tds_mg_l} onChange={(value) => updateField(setQuality, 'tds_mg_l', value)} min="0" step="1" /><Field label="Electrical Conductivity (EC)" unit="µS/cm" value={quality.ec_us_cm} onChange={(value) => updateField(setQuality, 'ec_us_cm', value)} min="0" step="1" /><Field label="Turbidity" unit="NTU" value={quality.turbidity_ntu} onChange={(value) => updateField(setQuality, 'turbidity_ntu', value)} min="0" step="0.1" optional /><Field label="Temperature" unit="°C" value={quality.temperature_c} onChange={(value) => updateField(setQuality, 'temperature_c', value)} min="-50" max="100" step="0.1" optional /><Field label="Total hardness" unit="mg/L as CaCO₃" value={quality.hardness_mg_l} onChange={(value) => updateField(setQuality, 'hardness_mg_l', value)} min="0" step="1" optional /><Field label="Chloride" unit="mg/L" value={quality.chloride_mg_l} onChange={(value) => updateField(setQuality, 'chloride_mg_l', value)} min="0" step="1" optional /></div> : <div className="form-grid three submission-fields"><Field label="Groundwater level" unit="m" value={groundwater.groundwater_level_m} onChange={(value) => updateField(setGroundwater, 'groundwater_level_m', value)} min="-1000" step="0.01" optional /><Field label="Distance sensor reading" unit="cm" value={groundwater.distance_cm} onChange={(value) => updateField(setGroundwater, 'distance_cm', value)} min="0" step="0.1" optional /><Field label="Water depth" unit="cm" value={groundwater.water_depth_cm} onChange={(value) => updateField(setGroundwater, 'water_depth_cm', value)} min="0" step="0.1" optional /><Field label="Water level" unit="%" value={groundwater.water_level_percent} onChange={(value) => updateField(setGroundwater, 'water_level_percent', value)} min="0" max="100" step="0.1" optional /><Field label="Rainfall observation" unit="mm" value={groundwater.rainfall_mm} onChange={(value) => updateField(setGroundwater, 'rainfall_mm', value)} min="0" step="0.1" optional /></div>}
      <div className="form-grid two submission-bottom"><label>Remarks<textarea value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="Context, instrument notes, weather, or observed anomalies" maxLength={2000} /></label><label>Proof photo or supporting report<input type="file" accept=".jpg,.jpeg,.png,.webp,.csv,.pdf,.txt,.xls,.xlsx,image/jpeg,image/png,image/webp" onChange={(event) => setAttachment(event.target.files?.[0] ?? null)} /><small className="field-help">Optional proof photo of the OLED/meter or report. Maximum 10 MB. Stored with the submission audit trail.</small></label></div>
      {error && <div className="form-message error"><AlertTriangle size={15} />{error}</div>}{message && <div className="form-message success"><CheckCircle2 size={15} />{message}</div>}
      <div className="submission-actions"><span className="field-help">Values are validated again on the server. Suspicious readings are flagged, not silently changed.</span><div><button className="button ghost" disabled={busy} onClick={() => submit(true)}><Save size={14} /> Save draft</button><button className="button primary" disabled={busy} onClick={() => submit(false)}><Send size={14} /> {busy ? 'Saving…' : 'Submit for review'}</button></div></div>
    </section>
  </>
}

function Field({ label, unit, value, onChange, min, max, step, optional }: { label: string; unit: string; value: string; onChange: (value: string) => void; min?: string; max?: string; step?: string; optional?: boolean }) {
  return <label>{label}{optional && <span className="optional-label">Optional</span>}<div className="unit-input"><input type="number" value={value} min={min} max={max} step={step} onChange={(event) => onChange(event.target.value)} placeholder="—" /><span>{unit}</span></div></label>
}

function MySubmissionsPage() {
  const [items, setItems] = useState<SubmissionRecord[]>([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = () => { setLoading(true); apiFetch<{ items: SubmissionRecord[]; total: number }>('/api/submissions/mine').then((result) => setItems(result.items)).catch(() => setItems(readStorage<SubmissionRecord[]>('local-submissions', []))).catch((loadError) => setError(loadError instanceof Error ? loadError.message : 'Unable to load submissions.')).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])
  const filtered = status ? items.filter((item) => item.status === status) : items
  return <><PageHeader eyebrow="Data submission · history" title="My submissions" description="Only your records are shown here. Review status and feedback remain attached to each original submission." action={<button className="button ghost" onClick={load}><RefreshCw size={14} /> Refresh</button>} /><div className="filter-row"><button className={`filter ${status === '' ? 'active' : ''}`} onClick={() => setStatus('')}>All <span>{items.length}</span></button>{['Draft', 'Submitted', 'Approved', 'Rejected', 'Correction Requested'].map((value) => <button className={`filter ${status === value ? 'active' : ''}`} key={value} onClick={() => setStatus(value)}>{value}</button>)}<span className="filter-spacer" /></div><section className="panel submission-table"><div className="table-row table-head submission-row"><span>Submission</span><span>Measured</span><span>Category</span><span>Status</span><span>Warnings</span><span>Version</span></div>{loading ? <div className="empty-module"><RefreshCw size={20} className="cyan-icon" /><p>Loading your submissions…</p></div> : error ? <div className="form-message error"><AlertTriangle size={15} />{error}</div> : filtered.length === 0 ? <div className="empty-module"><ClipboardCheck size={24} className="cyan-icon" /><h2>No records in this filter</h2><p>Submit a groundwater or water-quality observation to create the first auditable record.</p></div> : filtered.map((item) => <div className="table-row submission-row" key={item.id}><span><strong>{item.id.slice(0, 12)}</strong><small>{item.station_id}</small></span><span className="muted-cell">{new Date(item.measurement_at).toLocaleString()}</span><span>{item.quality ? 'Water quality' : 'Groundwater'}</span><span><span className={`submission-status ${item.status.toLowerCase().replaceAll(' ', '-')}`}>{item.status}</span></span><span className={item.validation_warnings.length ? 'warning-text' : 'muted-cell'}>{item.validation_warnings.length ? `${item.validation_warnings.length} flagged` : 'None'}</span><span>v{item.version}</span>{item.review_feedback && <small className="review-feedback">Feedback: {item.review_feedback}</small>}</div>)}</section></>
}

function NotificationsPage({ account }: { account: Account }) {
  const [enabled, setEnabled] = useState(Boolean(account.reminderConsent))
  const [weekday, setWeekday] = useState(0)
  const [localTime, setLocalTime] = useState('09:00')
  const [timezone, setTimezone] = useState(account.timezone || 'Asia/Kolkata')
  const [channels, setChannels] = useState<string[]>(account.preferredReminderChannel === 'both' ? ['email', 'sms'] : [account.preferredReminderChannel || 'email'])
  const [logs, setLogs] = useState<NotificationDelivery[]>([])
  const [message, setMessage] = useState('')
  type NotificationDelivery = { id: string; channel: string; status: string; scheduled_at: string; sent_at?: string | null; failure_reason?: string | null }
  useEffect(() => { apiFetch<{ channels: string[]; enabled: boolean; weekday: number; local_time: string; timezone: string }>('/api/reminders').then((schedule) => { setEnabled(schedule.enabled); setWeekday(schedule.weekday); setLocalTime(schedule.local_time); setTimezone(schedule.timezone); setChannels(schedule.channels) }).catch(() => undefined); apiFetch<NotificationDelivery[]>('/api/notifications').then(setLogs).catch(() => undefined) }, [])
  const toggleChannel = (channel: string) => setChannels((previous) => previous.includes(channel) ? previous.filter((item) => item !== channel) : [...previous, channel])
  const save = async () => { try { await apiFetch('/api/profile', { method: 'PATCH', body: JSON.stringify({ reminder_consent: enabled, preferred_reminder_channel: channels.length === 2 ? 'both' : channels[0] || 'email', timezone }) }); await apiFetch('/api/reminders', { method: 'PUT', body: JSON.stringify({ enabled, weekday, local_time: localTime, timezone, channels }) }); setMessage('Reminder preferences saved. The backend scheduler owns delivery and prevents duplicates.') } catch (saveError) { setMessage(saveError instanceof Error ? saveError.message : 'Unable to save reminder preferences.') } }
  return <><PageHeader eyebrow="Notifications · weekly" title="Reminder preferences" description="Weekly submission reminders run on the backend, respect your timezone, and never claim delivery when a provider is not configured." action={<button className="button primary" onClick={save}><Save size={14} /> Save preferences</button>} /><div className="metric-grid"><MetricCard label="Reminder status" value={enabled ? 'Enabled' : 'Paused'} detail="Persistent server-side schedule" icon={<CalendarDays size={17} />} tone={enabled ? undefined : 'amber'} /><MetricCard label="Channels" value={channels.length ? channels.join(' + ') : 'None'} detail="Only verified channels can send" icon={<Send size={17} />} /><MetricCard label="Timezone" value={timezone} detail="Local delivery time" icon={<Clock3 size={17} />} /><MetricCard label="Consent" value={account.reminderConsent ? 'Recorded' : 'Not recorded'} detail="Optional reminders" icon={<ShieldCheck size={17} />} /></div><div className="settings-grid"><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Weekly schedule</div><h2>Choose when to be reminded</h2></div></div><div className="form-grid two reminder-form"><label className="toggle-field"><span>Weekly reminders</span><button className={`toggle ${enabled ? 'on' : ''}`} onClick={() => setEnabled((value) => !value)} aria-pressed={enabled}><span /></button></label><label>Day<select value={weekday} onChange={(event) => setWeekday(Number(event.target.value))}>{['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label><label>Local delivery time<input type="time" value={localTime} onChange={(event) => setLocalTime(event.target.value)} /></label><label>Timezone<input value={timezone} onChange={(event) => setTimezone(event.target.value)} /></label></div><div className="channel-options"><span className="eyebrow">Preferred channels</span><button className={channels.includes('email') ? 'selected' : ''} onClick={() => toggleChannel('email')}><Mail size={15} />Email</button><button className={channels.includes('sms') ? 'selected' : ''} onClick={() => toggleChannel('sms')}><Phone size={15} />SMS</button></div><div className="setting-note"><ShieldCheck size={15} />Development mode records simulated messages only. Production email/SMS providers, consent and sender registration are required before real delivery.</div>{message && <div className="form-message success"><CheckCircle2 size={15} />{message}</div>}</section><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Delivery history</div><h2>Reminder log</h2></div></div>{logs.length === 0 ? <div className="empty-module"><Send size={22} className="cyan-icon" /><p>No reminder deliveries recorded yet.</p></div> : logs.slice(0, 10).map((log) => <div className="notification-row" key={log.id}><span className="notification-channel">{log.channel === 'email' ? <Mail size={14} /> : <Phone size={14} />}</span><div><strong>{log.channel} reminder</strong><span>{new Date(log.scheduled_at).toLocaleString()}</span></div><span className={`submission-status ${log.status}`}>{log.status}</span></div>)}</section></div></>
}

function LiveMonitoringPage({ location, geoStatus, requestLocation, role }: { location: LiveLocation | null; geoStatus: 'idle' | 'requesting' | 'granted' | 'denied'; requestLocation: () => void; role: Role }) {
  type LiveReading = { id: string; device_id: string; timestamp: string; created_at?: string; receivedAt?: number; distance_cm?: number | null; water_level_percent?: number | null; water_depth_cm?: number | null; quality_status: string; station_id?: string | null }
  const [history, setHistory] = useState<LiveReading[]>([])
  const [liveDevices, setLiveDevices] = useState<Record<string, LiveReading>>({})
  const [historyPaused, setHistoryPaused] = useState(false)
  const acceptReadings = (incoming: LiveReading[]) => {
    const stamped = incoming.map((reading) => ({ ...reading, receivedAt: Date.now() }))
    setLiveDevices((current) => {
      const next = { ...current }
      stamped.forEach((reading) => { next[reading.device_id] = reading })
      return next
    })
    if (!historyPaused) setHistory((current) => mergeLiveReadings(current, stamped))
  }
  const load = async () => {
    try {
      const next = await apiFetch<LiveReading[]>('/api/measurements?limit=20')
      acceptReadings(next)
    } catch {
      // Local preview sessions may predate backend authentication. Keep the
      // preview useful in development without weakening production routes.
      try {
        const response = await fetch(`${backendUrl}/api/measurements/live-preview?limit=12`)
        if (!response.ok) throw new Error('Live preview unavailable')
        const next = await response.json() as LiveReading[]
        acceptReadings(next)
      } catch {
        setHistory((current) => current)
      }
    }
  }
  useEffect(() => {
    load()
    let socket: WebSocket | null = null
    let reconnectTimer: number | undefined
    let disposed = false
    const connect = () => {
      if (disposed) return
      const token = readStorage<string | null>('api-token', null)
      socket = new WebSocket(`${backendUrl.replace(/^http/, 'ws')}/api/ws/measurements${token ? `?token=${encodeURIComponent(token)}` : ''}`)
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { measurement?: LiveReading }
          if (payload.measurement) acceptReadings([payload.measurement as LiveReading])
        } catch { /* ignore malformed websocket frames */ }
      }
      socket.onclose = () => { if (!disposed) reconnectTimer = window.setTimeout(connect, 1000) }
      socket.onerror = () => socket?.close()
    }
    connect()
    const fallbackTimer = window.setInterval(load, 2000)
    return () => { disposed = true; window.clearInterval(fallbackTimer); if (reconnectTimer) window.clearTimeout(reconnectTimer); socket?.close() }
  }, [historyPaused])
  const now = Date.now()
  const onlineDevices = Object.values(liveDevices).filter((reading) => reading.receivedAt != null && now - reading.receivedAt <= 10000)
  const latest = onlineDevices[0] ?? Object.values(liveDevices)[0] ?? history[0]
  const live = onlineDevices.length > 0
  return <><PageHeader eyebrow="Iot · live monitoring" title="Live monitoring" description="Each connected ESP32 has one live row. New packets replace that row immediately; the packet history can be cleared and paused below." action={<button className="button primary" onClick={requestLocation}><LocateFixed size={15} /> Sync location</button>} /><div className="demo-banner"><Radio size={15} /><span><strong>{live ? `${onlineDevices.length} ESP32 device${onlineDevices.length === 1 ? '' : 's'} connected` : location ? 'Site context linked' : 'Awaiting device data'}</strong> Live readings arrive over WebSocket. Raw readings stay pending until an administrator approves them.</span></div><div className="metric-grid"><MetricCard label="Device connection" value={live ? 'Online' : 'Waiting'} detail={latest ? `Last seen ${new Date(latest.timestamp).toLocaleTimeString()}` : 'Connect ESP32 or serial bridge'} icon={<Radio size={17} />} tone={live ? undefined : 'amber'} /><MetricCard label="Latest status" value={latest?.quality_status === 'reviewed' ? 'Approved' : latest ? 'Pending' : '—'} detail="Administrator review gate" icon={<ClipboardCheck size={17} />} /><MetricCard label="Distance reading" value={latest?.distance_cm != null ? `${latest.distance_cm.toFixed(1)} cm` : '—'} detail="Raw value received from ESP32" icon={<Gauge size={17} />} /><MetricCard label="Water level" value={latest?.water_level_percent != null ? `${latest.water_level_percent.toFixed(1)}%` : '—'} detail={location ? formatCoordinates(location) : 'Station location assigned'} icon={<MapPinned size={17} />} /></div><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Connected devices</div><h2>Current online readings</h2></div><button className="button ghost small" onClick={load}><RefreshCw size={14} /> Refresh</button></div>{onlineDevices.length === 0 ? <div className="empty-module"><Radio size={22} className="cyan-icon" /><h2>No online ESP32 devices</h2><p>Only devices heard from in the last 10 seconds appear in this pending-review list.</p></div> : onlineDevices.map((reading) => <div className="device-row" key={reading.device_id}><div className="device-icon"><Gauge size={15} /></div><div><strong>{reading.device_id}</strong><span>Updated {new Date(reading.timestamp).toLocaleTimeString()} · {reading.distance_cm?.toFixed(1) ?? '—'} cm · {reading.water_level_percent?.toFixed(1) ?? '—'}%</span></div><span className="quality-badge good"><span className="status-dot green" />Online · {reading.quality_status === 'pending_review' ? 'Pending review' : reading.quality_status === 'reviewed' ? 'Approved' : reading.quality_status}</span></div>)}</section><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Reading history</div><h2>Recent packet events</h2></div><div className="panel-actions"><span className="model-label">{history.length} retained</span><button className="button ghost small" onClick={() => { if (historyPaused) { setHistoryPaused(false) } else { setHistory([]); setHistoryPaused(true) } }}><X size={14} />{historyPaused ? ' Resume history' : ' Clear history'}</button></div></div>{history.length === 0 ? <div className="empty-module"><Clock3 size={22} className="cyan-icon" /><p>{historyPaused ? 'History paused. New packets will not be retained until resumed.' : 'No packets retained yet. New packets will appear here.'}</p></div> : history.slice(0, 12).map((reading) => <div className="device-row" key={reading.id}><div className="device-icon"><Clock3 size={15} /></div><div><strong>{reading.device_id}</strong><span>{new Date(reading.timestamp).toLocaleString()} · {reading.distance_cm?.toFixed(1) ?? '—'} cm · {reading.water_level_percent?.toFixed(1) ?? '—'}%</span></div><span className={`submission-status ${reading.quality_status === 'reviewed' ? 'approved' : reading.quality_status}`}>{reading.quality_status === 'pending_review' ? 'Pending review' : reading.quality_status === 'reviewed' ? 'Approved' : reading.quality_status}</span></div>)}</section><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Proof and approval</div><h2>Attach evidence before promotion</h2></div><Upload size={18} className="cyan-icon" /></div><p className="module-copy">For a reading that needs approval, open <strong>Submit monitoring data</strong>, choose Groundwater, enter or copy the live values, attach a photo of the OLED/meter reading, and submit it for administrator review. The photo and original values remain attached to the audit record.</p><div className="setting-note"><ShieldCheck size={15} />Pending device readings remain visible here but are excluded from official dashboard analytics until approved.</div></section></>
}

function mergeLiveReadings<T extends { id: string }>(current: T[], incoming: T[]) {
  return Array.from(new Map([...incoming, ...current].map((reading) => [reading.id, reading])).values()).slice(0, 100)
}

function MapLocationsPage({ location, geoStatus, requestLocation, onSelectLocation, accounts }: { location: LiveLocation | null; geoStatus: 'idle' | 'requesting' | 'granted' | 'denied'; requestLocation: () => void; onSelectLocation: (location: LiveLocation) => void; accounts: Account[] }) {
  return <><PageHeader eyebrow="Map · locations" title="Map and locations" description="Search a place, select a test area, and review shared monitoring locations." /><section className="panel module-map-panel"><LiveMap location={location} geoStatus={geoStatus} onRequest={requestLocation} onSelectLocation={onSelectLocation} accounts={accounts} /></section><div className="module-grid three"><MetricCard label="Mapped accounts" value={String(accounts.filter((account) => account.lastLocation).length)} detail="Locations shared in this workspace" icon={<Users size={17} />} /><MetricCard label="Selected site" value={location ? 'Ready' : 'Not set'} detail={location ? formatCoordinates(location) : 'Search or click the map'} icon={<MapPinned size={17} />} /><MetricCard label="Location privacy" value="Explicit" detail="Reverse geocoding requires an action" icon={<ShieldCheck size={17} />} /></div></>
}

function AdvisorPage({ values, prediction }: { values: Record<string, number>; prediction: { label: string; confidence: number | null } }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<{ question: string; answer: string }[]>([])
  const answerQuestion = (nextQuestion = question) => {
    const prompt = nextQuestion.trim()
    if (!prompt) return
    const lower = prompt.toLowerCase()
    const answer = lower.includes('quality') || lower.includes('wqi')
      ? `The current local screening is classified as ${prediction.label}. pH is ${values.pH.toFixed(2)}, TDS is ${Math.round(values.TDS_mg_L)} mg/L and EC is ${Math.round(values.EC_uS_cm)} µS/cm. A calibrated confidence score is unavailable, and this is not a potability certificate.`
      : lower.includes('conserve') ? 'Record levels consistently, investigate rapid declines, check leaks, stagger pumping and protect recharge areas before increasing extraction.'
        : lower.includes('level') || lower.includes('groundwater') ? 'The dashboard currently has a transparent screening workflow. A trained forecast is only shown when a compatible artifact is configured; otherwise the fallback is labelled clearly.'
          : 'I can explain the current screening result, groundwater status, forecast limitations, alerts and conservation actions using the values in this workspace.'
    setMessages((previous) => [...previous, { question: prompt, answer }])
    setQuestion('')
  }
  return <><PageHeader eyebrow="Ai · water advisor" title="AI water advisor" description="A deterministic local advisor that uses the current workspace values without inventing measurements." /><div className="advisor-layout"><section className="panel advisor-chat"><div className="panel-heading"><div><div className="eyebrow">Contextual assistant</div><h2>Ask about this workspace</h2></div><span className="quality-badge good"><span className="status-dot green" />Local mode</span></div><div className="advisor-messages">{messages.length === 0 ? <div className="empty-state"><Sparkles size={16} className="cyan-icon" />Ask a question to generate a grounded explanation.</div> : messages.map((message, index) => <div className="advisor-message" key={`${message.question}-${index}`}><strong>{message.question}</strong><p>{message.answer}</p></div>)}</div><form className="advisor-form" onSubmit={(event) => { event.preventDefault(); answerQuestion() }}><input aria-label="Ask the water advisor" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What does my WQI mean?" /><button className="button primary" type="submit"><ArrowUpRight size={14} /> Ask</button></form></section><section className="panel prompt-panel"><div className="panel-heading"><div><div className="eyebrow">Suggested prompts</div><h2>Start with a question</h2></div></div>{['What does my water quality result mean?', 'What is the groundwater status?', 'How can I conserve groundwater?', 'What do the forecast limitations mean?'].map((prompt) => <button className="prompt-button" key={prompt} onClick={() => answerQuestion(prompt)}><Sparkles size={14} />{prompt}<ArrowUpRight size={13} /></button>)}</section></div></>
}

function HistoryAnalyticsPage({ values, location }: { values: Record<string, number>; location: LiveLocation | null }) {
  const [range, setRange] = useState('24h')
  const exportCsv = () => {
    const rows = [['parameter', 'value', 'unit', 'source'], ['pH', values.pH.toFixed(2), 'pH', 'manual workspace reading'], ['EC', String(Math.round(values.EC_uS_cm)), 'µS/cm', 'manual workspace reading'], ['TDS', String(Math.round(values.TDS_mg_L)), 'mg/L', 'manual workspace reading']]
    const blob = new Blob([rows.map((row) => row.join(',')).join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'hydroinsight-history.csv'; anchor.click(); URL.revokeObjectURL(url)
  }
  return <><PageHeader eyebrow="Analytics · history" title="History and analytics" description="Filter the selected workspace readings and export the same dataset used in the summary." action={<button className="button ghost" onClick={exportCsv}><FileText size={15} /> Export CSV</button>} /><div className="filter-row"><button className={`filter ${range === '24h' ? 'active' : ''}`} onClick={() => setRange('24h')}>24 hours</button><button className={`filter ${range === '7d' ? 'active' : ''}`} onClick={() => setRange('7d')}>7 days</button><button className={`filter ${range === '30d' ? 'active' : ''}`} onClick={() => setRange('30d')}>30 days</button><span className="filter-spacer" /><span className="quality-badge good"><span className="status-dot green" />{location ? 'Site linked' : 'No site selected'}</span></div><div className="metric-grid"><MetricCard label="Selected range" value={range} detail="Date filter applied to this view" icon={<RefreshCw size={17} />} /><MetricCard label="Available values" value="5" detail="Configured quality parameters" icon={<Activity size={17} />} /><MetricCard label="Data quality" value="Manual" detail="Clearly marked source" icon={<ShieldCheck size={17} />} /><MetricCard label="Missing series" value="—" detail="Backend import required" icon={<Cloud size={17} />} /></div><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Current workspace reading</div><h2>Filter-consistent table</h2></div><span className="model-label">{range}</span></div><div className="table-row table-head history-row"><span>Parameter</span><span>Value</span><span>Unit</span><span>Source</span></div>{parameterConfig.map((config) => <div className="table-row history-row" key={config.key}><span>{config.name}</span><strong>{formatValue(values[config.key], config)}</strong><span className="muted-cell">{config.unit}</span><span className="muted-cell">Manual workspace</span></div>)}</section></>
}

function DevicesStationsPage({ role, location }: { role: Role; location: LiveLocation | null }) {
  const [deviceName, setDeviceName] = useState('')
  const [devices, setDevices] = useState([{ id: 'ESP32-DEMO-001', name: 'Demo ultrasonic level sensor', status: 'Demo offline' }])
  const addDevice = (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!deviceName.trim()) return; setDevices((previous) => [...previous, { id: `ESP32-${previous.length + 1}`.padEnd(12, '0'), name: deviceName.trim(), status: 'Registered locally' }]); setDeviceName('') }
  return <><PageHeader eyebrow="Iot · devices and stations" title="Devices and stations" description="Register ESP32 devices, assign stations, and keep hardware status explicit." action={role === 'admin' ? <form className="inline-add-form" onSubmit={addDevice}><input aria-label="Device name" value={deviceName} onChange={(event) => setDeviceName(event.target.value)} placeholder="New device name" /><button className="button primary" type="submit"><Zap size={14} /> Register</button></form> : undefined} /><div className="module-grid three"><MetricCard label="Registered devices" value={String(devices.length)} detail="Local workspace registry" icon={<Zap size={17} />} /><MetricCard label="Stations" value={location ? '1' : '0'} detail={location ? 'Current test site' : 'Add a site from the map'} icon={<MapPinned size={17} />} /><MetricCard label="Permissions" value={role === 'admin' ? 'Admin write' : 'Read only'} detail="Backend protects device changes" icon={<ShieldCheck size={17} />} /></div><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Device registry</div><h2>Connected hardware</h2></div><span className="quality-badge amber"><span className="status-dot amber" />No live Wi-Fi</span></div>{devices.map((device) => <div className="device-row" key={device.id}><div className="device-icon"><Zap size={15} /></div><div><strong>{device.name}</strong><span>{device.id} · {device.status}</span></div><span className="status-pill marginal">Offline-safe</span></div>)}</section></>
}

function EducationPage() {
  return <><PageHeader eyebrow="Learn · resources" title="Education and resources" description="Practical guidance for interpreting sensor screening and groundwater trends." /><div className="module-grid three"><section className="panel resource-card"><span className="resource-icon"><Droplets size={18} /></span><h2>Understand quality screening</h2><p>The current screening profile uses pH, TDS, turbidity and temperature. It is not a potability certification; laboratory testing remains necessary for health-critical decisions.</p><button className="text-button">View methodology <ArrowUpRight size={14} /></button></section><section className="panel resource-card"><span className="resource-icon"><Gauge size={18} /></span><h2>Read depletion risk</h2><p>Use consistent station readings, seasonal context and uncertainty. A transparent temporal trend forecast is not the same as a trained forecasting model.</p><button className="text-button">View forecast guidance <ArrowUpRight size={14} /></button></section><section className="panel resource-card"><span className="resource-icon"><ShieldCheck size={18} /></span><h2>Review the evidence boundary</h2><p>Every reading keeps its source, timestamp, location, validation state and approval history. Unapproved readings are excluded from official analytics.</p><button className="text-button">View limitations <ArrowUpRight size={14} /></button></section></div></>
}

function HelpPage() {
  return <><PageHeader eyebrow="Support · documentation" title="Help and support" description="Setup guidance for the frontend, FastAPI backend, datasets and ESP32 serial bridge." /><div className="module-grid two"><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Quick start</div><h2>Run the full stack</h2></div></div><ol className="help-list"><li>Run <span className="mono">npm run dev</span> for the frontend.</li><li>Install <span className="mono">py -3 -m pip install -r backend/requirements.txt</span>.</li><li>Run <span className="mono">py -3 -m uvicorn app.main:app --reload --app-dir backend</span>.</li><li>Open <span className="mono">http://127.0.0.1:8000/docs</span> for API documentation.</li></ol></section><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Troubleshooting</div><h2>Common states</h2></div></div><div className="help-item"><strong>Hardware offline</strong><span>Register a device and run the serial bridge; no offline preview is presented as live.</span></div><div className="help-item"><strong>Location denied</strong><span>Use the map search or explicit point selection to attach a site to the test.</span></div><div className="help-item"><strong>Dataset import</strong><span>Run the importer to inspect columns before mapping date, station and level fields.</span></div></section></div></>
}

function PolicyPage({ kind }: { kind: 'privacy' | 'terms' }) {
  const privacy = kind === 'privacy'
  return <><PageHeader eyebrow="Legal · review required" title={privacy ? 'Privacy policy' : 'Terms of service'} description="Draft product notice for academic/project deployment. Obtain legal review before production use." /><section className="panel module-card policy-copy"><h2>{privacy ? 'How AquaSense handles data' : 'Using AquaSense responsibly'}</h2><p>AquaSense stores account details, approved monitoring submissions, optional proof attachments, device diagnostics and site coordinates only to operate the monitoring workflow.</p><h3>Choices and rights</h3><p>You can choose essential-only cookies, export your account data, request deletion, and withdraw optional reminders or marketing contact. Data is not sold and customer data is not used to train external AI models.</p><h3>Retention and safety</h3><p>Project operators must configure retention limits, backups, access roles and deletion schedules. Health, drinking-water and regulatory decisions require laboratory verification.</p><h3>Third parties and accessibility</h3><p>Maps use OpenStreetMap, Esri, OpenTopoMap and Nominatim where enabled. Review their terms and licence obligations. AI-generated summaries are labelled and should be checked by a human.</p><p className="setting-note">Business contact, jurisdiction, refund language, parental-consent handling, DPAs and statutory registration requirements must be completed by the deploying organisation and reviewed by qualified counsel.</p></section></>
}

function ProfilePage({ account, onAccountUpdate }: { account: Account; onAccountUpdate: (patch: Partial<Account>) => void }) {
  const [name, setName] = useState(account.name)
  const [saved, setSaved] = useState(false)
  const [verificationCode, setVerificationCode] = useState('')
  const [verificationChannel, setVerificationChannel] = useState<'email' | 'mobile'>('email')
  const [verificationMessage, setVerificationMessage] = useState('')
  const [verificationError, setVerificationError] = useState('')
  const requestCode = async () => { try { const result = await apiFetch<{ message: string; development_code?: string }>('/api/verification/request', { method: 'POST', body: JSON.stringify({ channel: verificationChannel }) }); setVerificationMessage(result.development_code ? `${result.message} Development code: ${result.development_code}` : result.message); setVerificationError('') } catch (error) { setVerificationError(error instanceof Error ? error.message : 'Unable to request verification.') } }
  const confirmCode = async () => { try { const result = await apiFetch<{ email_verified: boolean; mobile_verified: boolean }>('/api/verification/confirm', { method: 'POST', body: JSON.stringify({ channel: verificationChannel, code: verificationCode }) }); onAccountUpdate({ emailVerified: result.email_verified, mobileVerified: result.mobile_verified }); setVerificationMessage(`${verificationChannel === 'email' ? 'Email' : 'Mobile'} verified.`); setVerificationError('') } catch (error) { setVerificationError(error instanceof Error ? error.message : 'Unable to verify contact.') } }
  const saveProfile = async () => { try { const result = await apiFetch<{ name: string }>('/api/profile', { method: 'PATCH', body: JSON.stringify({ name: name.trim() || account.name }) }); onAccountUpdate({ name: result.name }); setSaved(true) } catch { onAccountUpdate({ name: name.trim() || account.name }); setSaved(true) } }
  return <><PageHeader eyebrow="Account · profile" title="User profile" description="Manage identity, contact verification and the permissions assigned to this account." /><div className="profile-grid"><section className="panel module-card profile-card"><div className="profile-avatar">{account.role === 'admin' ? 'AD' : 'US'}</div><div className="profile-fields"><label>Full name<input value={name} onChange={(event) => setName(event.target.value)} /></label><label>Email address<input value={account.email} disabled /></label><label>Mobile number<input value={account.mobileNumber || 'Not provided'} disabled /></label><div className="profile-role"><span className="eyebrow">Role and access</span><strong>{account.role === 'admin' ? 'Administrator' : 'Standard user'}</strong><span>{account.role === 'admin' ? 'Can manage users, stations, submissions and system health.' : 'Can submit readings and review your own history.'}</span></div><button className="button primary" onClick={saveProfile}><Save size={14} />{saved ? 'Profile saved' : 'Save profile'}</button></div></section><section className="panel module-card verification-panel"><div className="panel-heading"><div><div className="eyebrow">Contact verification</div><h2>Verify delivery channels</h2></div><UserCheck size={18} className="cyan-icon" /></div><VerificationRow label="Email" value={account.email} verified={Boolean(account.emailVerified)} /><VerificationRow label="Mobile" value={account.mobileNumber || 'Not provided'} verified={Boolean(account.mobileVerified)} /><div className="verification-actions"><select value={verificationChannel} onChange={(event) => setVerificationChannel(event.target.value as 'email' | 'mobile')}><option value="email">Email verification</option><option value="mobile">Mobile verification</option></select><button className="button ghost" onClick={requestCode}><Send size={14} /> Request code</button><input aria-label="Verification code" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value)} placeholder="6-digit code" maxLength={6} /><button className="button primary" onClick={confirmCode}><Check size={14} /> Confirm</button></div>{verificationMessage && <div className="form-message success"><CheckCircle2 size={15} />{verificationMessage}</div>}{verificationError && <div className="form-message error"><AlertTriangle size={15} />{verificationError}</div>}<div className="setting-note"><ShieldCheck size={15} />Contact details remain unverified until the code is confirmed. Provider delivery is simulated only in development mode.</div></section></div></>
}

function VerificationRow({ label, value, verified }: { label: string; value: string; verified: boolean }) { return <div className="verification-row"><span>{label}</span><strong>{value}</strong><span className={`submission-status ${verified ? 'approved' : 'unverified'}`}>{verified ? 'Verified' : 'Unverified'}</span></div> }

function AdminPage({ accounts }: { accounts: Account[] }) {
  const [stats, setStats] = useState<{ total_users: number; verified_users: number; active_stations: number; total_submissions: number; awaiting_review: number; approved_submissions: number; rejected_submissions: number; failed_reminders: number; warning_count: number } | null>(null)
  const [queue, setQueue] = useState<SubmissionRecord[]>([])
  const [deviceQueue, setDeviceQueue] = useState<DeviceReviewRecord[]>([])
  const [message, setMessage] = useState('')
  const load = () => { apiFetch<typeof stats>('/api/admin/stats').then(setStats).catch(() => setStats(null)); apiFetch<{ items: SubmissionRecord[] }>('/api/admin/submissions?status=Submitted').then((result) => setQueue(result.items)).catch(() => setQueue(readStorage<SubmissionRecord[]>('local-submissions', []).filter((item) => item.status === 'Submitted'))); apiFetch<DeviceReviewRecord[]>('/api/admin/measurements?status=pending_review&limit=40').then(setDeviceQueue).catch(() => fetch(`${backendUrl}/api/admin/measurements/live-preview?status=pending_review&limit=40`).then((response) => response.ok ? response.json() as Promise<DeviceReviewRecord[]> : Promise.reject()).then(setDeviceQueue).catch(() => setDeviceQueue([]))) }
  useEffect(() => { load() }, [])
  const review = async (id: string, status: 'Approved' | 'Rejected' | 'Correction Requested') => { const reason = status === 'Approved' ? undefined : window.prompt(status === 'Rejected' ? 'Required rejection reason' : 'Required correction request') || ''; if (status !== 'Approved' && !reason) return; try { await apiFetch(`/api/admin/submissions/${id}/review`, { method: 'POST', body: JSON.stringify({ status, reason }) }) } catch { const local = readStorage<SubmissionRecord[]>('local-submissions', []); writeStorage('local-submissions', local.map((item) => item.id === id ? { ...item, status, review_feedback: reason } : item)) } setMessage(`Submission ${status.toLowerCase()}.`); load() }
  const reviewDevice = async (id: string, status: 'Approved' | 'Rejected') => { const reason = status === 'Rejected' ? window.prompt('Required rejection reason') || '' : undefined; if (status === 'Rejected' && !reason) return; try { try { await apiFetch(`/api/admin/measurements/${id}/review`, { method: 'POST', body: JSON.stringify({ status, reason }) }) } catch { await fetch(`${backendUrl}/api/admin/measurements/live-preview/${id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, reason }) }) } setMessage(`Device reading ${status.toLowerCase()}. Admin notification recorded.`); load() } catch (error) { setMessage(error instanceof Error ? error.message : 'Device review failed.') } }
  return <><PageHeader eyebrow="Admin · data management" title="Administration" description="Review submissions, monitor delivery health and control which data enters approved analytics." action={<button className="button ghost" onClick={load}><RefreshCw size={14} /> Refresh queue</button>} /><div className="metric-grid"><MetricCard label="Registered users" value={String(stats?.total_users ?? accounts.length)} detail={`${stats?.verified_users ?? 0} fully verified`} icon={<Users size={17} />} /><MetricCard label="Total submissions" value={String(stats?.total_submissions ?? 0)} detail={`${stats?.awaiting_review ?? 0} awaiting review`} icon={<Database size={17} />} /><MetricCard label="Approved data" value={String(stats?.approved_submissions ?? 0)} detail="Eligible for analytics" icon={<CheckCircle2 size={17} />} /><MetricCard label="Reminder failures" value={String(stats?.failed_reminders ?? 0)} detail={`${stats?.warning_count ?? 0} data-quality warnings`} icon={<Send size={17} />} tone={stats?.failed_reminders ? 'amber' : undefined} /></div><div className="admin-management-grid"><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Device review queue</div><h2>ESP32 readings awaiting promotion</h2></div><span className="quality-badge amber"><Radio size={14} />{deviceQueue.length} pending</span></div>{deviceQueue.length === 0 ? <div className="empty-module"><Radio size={24} className="cyan-icon" /><h2>No device readings waiting</h2><p>Connected ESP32 packets appear here as pending until an administrator reviews them.</p></div> : deviceQueue.slice(0, 12).map((item) => <div className="review-row" key={item.id}><div><strong>{item.device_id}</strong><span>{new Date(item.timestamp).toLocaleString()} · {item.distance_cm?.toFixed(1) ?? '—'} cm · {item.water_level_percent?.toFixed(1) ?? '—'}%</span><small>{item.site_latitude != null ? `Site ${item.site_latitude.toFixed(5)}, ${item.site_longitude?.toFixed(5)}` : 'No site snapshot attached'}</small></div><div className="review-actions"><button className="button primary small" onClick={() => reviewDevice(item.id, 'Approved')}><Check size={13} />Promote</button><button className="icon-button" aria-label={`Reject device reading ${item.device_id}`} onClick={() => reviewDevice(item.id, 'Rejected')}><AlertTriangle size={15} /></button></div></div>)}</section><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">Submission review queue</div><h2>New data awaiting review</h2></div><span className="quality-badge amber"><Clock3 size={14} />{queue.length} pending</span></div>{queue.length === 0 ? <div className="empty-module"><ClipboardCheck size={24} className="cyan-icon" /><h2>Queue is clear</h2><p>Submitted records will appear here before they are promoted to analytics.</p></div> : queue.map((item) => <div className="review-row" key={item.id}><div><strong>{item.id.slice(0, 12)}</strong><span>{item.quality ? 'Water quality' : 'Groundwater'} · {new Date(item.measurement_at).toLocaleString()}</span><small>{item.validation_warnings.length ? `${item.validation_warnings.length} warning(s)` : 'No validation warnings'}</small></div><div className="review-actions"><button className="button ghost small" onClick={() => review(item.id, 'Correction Requested')}>Request correction</button><button className="button primary small" onClick={() => review(item.id, 'Approved')}><Check size={13} />Approve</button><button className="icon-button" aria-label="Reject submission" onClick={() => review(item.id, 'Rejected')}><AlertTriangle size={15} /></button></div></div>)}</section><section className="panel module-card"><div className="panel-heading"><div><div className="eyebrow">User management</div><h2>Workspace accounts</h2></div><span className="quality-badge good"><ShieldCheck size={14} />Admin only</span></div>{accounts.map((account) => <div className="device-row" key={account.id}><div className="device-icon"><Users size={15} /></div><div><strong>{account.name}</strong><span>{account.email} · {account.role}</span></div><span className="status-pill within">Active</span></div>)}</section></div>{message && <div className="form-message success"><CheckCircle2 size={15} />{message}</div>}<div className="setting-note"><ShieldCheck size={15} />Backend permissions are enforced on every review route. Device promotion and user-submission review both create audit and admin notification records. Rejected and unreviewed submissions remain preserved and cannot become training data.</div></>
}

function AccessDeniedPage() {
  return <><PageHeader eyebrow="Administration" title="Access restricted" description="This area is available only to administrator accounts." /><section className="panel module-card empty-module"><ShieldCheck size={26} className="cyan-icon" /><h2>Administrator permission required</h2><p>Sign in with the workspace administrator account to manage users, devices and system health.</p></section></>
}

function MetricCard({ label, value, detail, icon, trend, positive, tone }: { label: string; value: string; detail: string; icon: ReactNode; trend?: string; positive?: boolean; tone?: string }) { return <div className={`metric-card ${tone ?? ''}`}><div className="metric-top"><span className="metric-icon">{icon}</span>{trend && <span className={`metric-trend ${positive ? 'positive' : ''}`}><ArrowUpRight size={13} />{trend}</span>}</div><strong className="metric-value">{value}</strong><span className="metric-label">{label}</span><span className="metric-detail">{detail}</span></div> }
function SiteRow({ name, type, status, quality, level, selected, warning }: { name: string; type: string; status: string; quality: string; level: string; selected?: boolean; warning?: boolean }) { return <div className={`table-row ${selected ? 'selected-row' : ''}`}><span className="site-name"><span className={`table-site-dot ${warning ? 'warning' : ''}`} /><span><strong>{name}</strong><small>{type}</small></span></span><span><span className={`row-status ${warning ? 'warning' : ''}`}><span className="status-dot" />{status}</span></span><span className="quality-cell">{quality}</span><span className={warning ? 'red-text' : ''}>{level}</span></div> }
function MiniStat({ label, value, status }: { label: string; value: string; status: string }) { return <div className="mini-stat"><span>{label}</span><strong>{value}</strong><small><span className="status-dot green" />{status}</small></div> }
function AlertItem({ title, meta, tone }: { title: string; meta: string; tone: string }) { return <div className="alert-item"><span className={`alert-icon ${tone}`}><AlertTriangle size={14} /></span><div><strong>{title}</strong><span>{meta}</span></div><ChevronDown size={14} className="muted-icon" /></div> }
function AlertTableRow({ title, site, time, severity, state, tone }: { title: string; site: string; time: string; severity: string; state: string; tone: string }) { return <div className="table-row"><span className="alert-title"><span className={`alert-icon ${tone}`}><AlertTriangle size={13} /></span><strong>{title}</strong></span><span>{site}</span><span className="muted-cell">{time}</span><span><span className={`severity ${tone}`}>{severity}</span></span><span><span className={`state ${state.toLowerCase()}`}>{state}</span></span><button className="icon-button"><MoreHorizontal size={16} /></button></div> }
function ReportRow({ name, site, time, classification }: { name: string; site: string; time: string; classification: string }) { return <div className="table-row"><span className="report-name"><FileText size={16} /><strong>{name}</strong></span><span>{site}</span><span className="muted-cell">{time}</span><span className="quality-cell">{classification}</span><span className="file-type">PDF</span><button className="icon-button"><MoreHorizontal size={16} /></button></div> }

function AuthScreen({ accounts, onAuthenticated }: { accounts: Account[]; onAuthenticated: (account: Account, nextAccounts?: Account[]) => void }) {
  const [mode, setMode] = useState<AuthMode>('signin')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [reminderConsent, setReminderConsent] = useState(false)
  const [resetToken, setResetToken] = useState('')
  const [error, setError] = useState('')

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail) {
      setError('Enter your email to continue.')
      return
    }
    if (mode === 'forgot') {
      if (!resetToken) {
        try {
          const headers = new Headers({ 'Content-Type': 'application/json' })
          const csrf = document.cookie.split('; ').find((item) => item.startsWith('aquasense_csrf='))?.split('=')[1]
          if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf))
          const response = await fetch(`${backendUrl}/api/auth/forgot-password`, { method: 'POST', headers, body: JSON.stringify({ email: normalizedEmail }), credentials: 'include' })
          const data = await response.json().catch(() => ({})) as { message?: string; development_token?: string; detail?: string }
          if (!response.ok) throw new Error(data.detail || 'Unable to start password reset')
          setResetToken(data.development_token || '')
          setError(data.message || 'Reset instructions have been requested.')
        } catch (forgotError) {
          setError(forgotError instanceof TypeError ? 'Password reset needs the FastAPI backend and an email provider.' : forgotError instanceof Error ? forgotError.message : 'Unable to start password reset')
        }
        return
      }
      if (password.length < 8) {
        setError('Use a new password with at least 8 characters.')
        return
      }
      try {
          const headers = new Headers({ 'Content-Type': 'application/json' })
          const csrf = document.cookie.split('; ').find((item) => item.startsWith('aquasense_csrf='))?.split('=')[1]
          if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf))
          const response = await fetch(`${backendUrl}/api/auth/reset-password`, { method: 'POST', headers, body: JSON.stringify({ token: resetToken, new_password: password }), credentials: 'include' })
        const data = await response.json().catch(() => ({})) as { message?: string; detail?: string }
        if (!response.ok) throw new Error(data.detail || 'Unable to reset password')
        setMode('signin')
        setResetToken('')
        setPassword('')
        setError(data.message || 'Password updated. Sign in with the new password.')
      } catch (resetError) {
        setError(resetError instanceof TypeError ? 'Password reset needs the FastAPI backend.' : resetError instanceof Error ? resetError.message : 'Unable to reset password')
      }
      return
    }
    if (!password) {
      setError('Enter your password to continue.')
      return
    }
    if (mode === 'signup') {
      if (!name.trim()) {
        setError('Enter a name for this account.')
        return
      }
      if (!/^\+?[1-9][\d\s().-]{7,18}$/.test(mobileNumber.trim())) {
        setError('Enter a mobile number with country code, for example +919876543210.')
        return
      }
      if (password.length < 8 || password !== passwordConfirmation) {
        setError('Use at least 8 characters and make both passwords match.')
        return
      }
      if (accounts.some((account) => account.email === normalizedEmail)) {
        setError('An account with this email already exists. Sign in instead.')
        return
      }
      try {
        const result = await backendAuth('signup', { name: name.trim(), email: normalizedEmail, mobile_number: mobileNumber.trim(), password, password_confirmation: passwordConfirmation, reminder_consent: String(reminderConsent), preferred_reminder_channel: 'email', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata' })
        const account: Account = { ...accountFromBackend(result.user), lastLocation: null }
        writeStorage('api-token', result.token)
        onAuthenticated(account, [...accounts, account])
        return
      } catch (backendError) {
        if (!(backendError instanceof TypeError)) {
          setError(backendError instanceof Error ? backendError.message : 'Unable to create the backend account.')
          return
        }
      }
      setError('Backend is unavailable. Local account creation is disabled so passwords are never stored in the browser.')
      return
    }
    try {
      const result = await backendAuth('signin', { email: normalizedEmail, password })
      const existing = accounts.find((candidate) => candidate.email === normalizedEmail)
      const account: Account = existing ? { ...existing, ...accountFromBackend(result.user), lastLocation: existing.lastLocation } : { ...accountFromBackend(result.user), lastLocation: null }
      const nextAccounts = existing ? accounts.map((candidate) => candidate.id === existing.id ? account : candidate) : [...accounts, account]
      writeStorage('api-token', result.token)
      onAuthenticated(account, nextAccounts)
      return
    } catch (backendError) {
      setError(backendError instanceof TypeError ? 'Backend is unavailable. Start FastAPI before signing in.' : backendError instanceof Error ? backendError.message : 'Unable to sign in to the backend.')
    }
  }

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode)
    setError('')
  }

  return <main className="auth-shell"><section className="auth-hero"><div className="brand-mark large"><Waves size={19} /></div><div className="eyebrow">Aquasense ai · water intelligence</div><h1>Evidence for every<br /><span>water decision.</span></h1><p>Field-ready monitoring for groundwater teams. Submit validated observations, retain the original record, and keep review boundaries clear.</p><div className="auth-feature-row"><span><MapPinned size={15} />Site-aware submissions</span><span><ShieldCheck size={15} />Auditable review</span><span><Users size={15} />Team permissions</span></div></section><section className="auth-card"><div className="auth-card-header"><div><div className="eyebrow">{mode === 'signin' ? 'RETURNING OPERATOR' : mode === 'signup' ? 'NEW OPERATOR' : 'RESET ACCESS'}</div><h2>{mode === 'signin' ? 'Sign in to AquaSense AI' : mode === 'signup' ? 'Create your AquaSense account' : 'Reset your password'}</h2></div><div className="auth-logo-badge"><Droplets size={17} /></div></div><p className="auth-subtitle">{mode === 'signin' ? 'Use your account to open the monitoring workspace.' : mode === 'signup' ? 'Create an account with verified contact details for weekly reminders.' : 'Request a development reset token, then choose a new password.'}</p><form className="auth-form" onSubmit={submit}>{mode === 'signup' && <><label>Full name<input className="auth-input" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Your full name" /></label><label>Mobile number<input className="auth-input" type="tel" autoComplete="tel" value={mobileNumber} onChange={(event) => setMobileNumber(event.target.value)} placeholder="+91 98765 43210" /></label></>}<label>Email address<input className="auth-input" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>{mode === 'forgot' && resetToken && <label>Reset token<input className="auth-input" value={resetToken} onChange={(event) => setResetToken(event.target.value)} placeholder="Paste the development token" /></label>}{(mode !== 'forgot' || resetToken) && <label>{mode === 'forgot' ? 'New password' : 'Password'}<input className="auth-input" type="password" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'forgot' ? 'At least 8 characters' : 'At least 8 characters'} /></label>}{mode === 'signup' && <label>Confirm password<input className="auth-input" type="password" autoComplete="new-password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="Repeat your password" /></label>}{mode === 'signup' && <label className="consent-field"><input type="checkbox" checked={reminderConsent} onChange={(event) => setReminderConsent(event.target.checked)} /><span>I consent to optional weekly monitoring reminders by email. I can change this later.</span></label>}{error && <p className="auth-error" role="alert">{error}</p>}<button className="auth-submit" type="submit">{mode === 'signin' ? <><LogIn size={16} /> Sign in</> : mode === 'signup' ? <><UserPlus size={16} /> Create account</> : resetToken ? <><ShieldCheck size={16} /> Reset password</> : <><LogIn size={16} /> Send reset instructions</>}</button></form><div className="auth-divider"><span>{mode === 'forgot' ? 'Remembered your password?' : mode === 'signin' ? 'New to the workspace?' : 'Already have an account?'}</span><button className="auth-toggle" onClick={() => switchMode(mode === 'forgot' ? 'signin' : mode === 'signin' ? 'signup' : 'signin')}>{mode === 'forgot' || mode === 'signup' ? 'Sign in instead' : 'Create an account'}</button></div>{mode !== 'forgot' && <button className="auth-toggle auth-forgot-link" onClick={() => { setMode('forgot'); setError(''); setResetToken('') }}>Forgot password?</button>}<p className="auth-note"><ShieldCheck size={14} /> Contact verification is explicit. Development mode may show a code; production delivery requires configured providers.</p></section></main>
}

function RootApp() {
  const [accounts, setAccounts] = useState<Account[]>(() => persistedAccounts(readStorage<Account[]>('accounts', [])))
  const [sessionId, setSessionId] = useState<string | null>(() => readStorage<string | null>('session-id', null))
  const currentAccount = accounts.find((account) => account.id === sessionId) ?? null

  const authenticate = (account: Account, nextAccounts = accounts) => {
    setAccounts(nextAccounts)
    writeStorage('accounts', persistedAccounts(nextAccounts))
    setSessionId(account.id)
    writeStorage('session-id', account.id)
  }

  const updateAccount = (patch: Partial<Account>) => {
    if (!currentAccount) return
    setAccounts((previous) => {
      const next = previous.map((account) => account.id === currentAccount.id ? { ...account, ...patch } : account)
      writeStorage('accounts', persistedAccounts(next))
      return next
    })
  }

  const signOut = () => {
    setSessionId(null)
    writeStorage('session-id', null)
    writeStorage('api-token', null)
  }

  if (!currentAccount) return <AuthScreen accounts={accounts} onAuthenticated={authenticate} />
  return <App accounts={accounts} currentAccount={currentAccount} onAccountUpdate={updateAccount} onSignOut={signOut} />
}

export default RootApp

createRoot(document.getElementById('root')!).render(<RootApp />)
