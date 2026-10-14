// Regenerates the homepage screenshots in src/landing/images/.
//
// They are screenshots of the real application, running locally, with the
// API's answers replaced *in the browser* by the sample company below --
// nothing is written to any database, and the app itself is unmodified.
// That keeps the pictures honest about what the screens look like while
// showing them with believable data rather than an empty dev tenant.
//
// Needs the dev servers running (make backend, make frontend), a local user
// to sign in as, Chrome, and puppeteer-core (not a project dependency):
//
//   npm install --no-save puppeteer-core
//   LANDING_USER=admin LANDING_PASSWORD=... node scripts/landing-screenshots.cjs
//
// Optional: CHROME_PATH, APP_URL (default http://localhost:5173).
const path = require('path')
const puppeteer = require('puppeteer-core')

const APP = process.env.APP_URL || 'http://localhost:5173'
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const OUT = path.join(__dirname, '..', 'src', 'landing', 'images')
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const MONTHS = ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
const REVENUE = [1820000, 1955000, 1712000, 2048000, 2213000, 2389000, 2294000, 2517000, 2632000, 2478000, 2815000, 1643000]
const EXPENSES = [1510000, 1623000, 1589000, 1664000, 1718000, 1892000, 1765000, 1843000, 2019000, 1934000, 2076000, 1182000]
const trend = (values, labels = MONTHS.slice(-values.length)) => values.map((value, i) => ({ label: labels[i], value: String(value) }))
const points = (pairs) => pairs.map(([label, value]) => ({ label, value: String(value) }))

const TEXT = {
  en: {
    user: 'Ayşe Demir',
    company: 'Demir Yapı Market A.Ş.',
    conversationTitle: 'Which customer invoices are overdue?',
    otherConversations: ['Stock that will run out this week', 'October payroll cost', 'Top vendors this quarter'],
    q1: 'Which customer invoices are overdue?',
    a1: 'Three customer invoices are overdue, **₺42,600** in total. The largest is Ege Lojistik at ₺21,400, now 34 days late. They are listed in the table below.',
    t1: 'Overdue customer invoices',
    q2: 'Show revenue by month this year as a chart',
    a2: 'Revenue this year peaked in September at **₺2,815,000**. October is still in progress. The chart below shows each month.',
    t2: 'Revenue by month, 2026',
    q3: 'Create an invoice for Anadolu Yapı: 12 pallets of cement at 3,450 each',
    a3: 'I have prepared the invoice for Anadolu Yapı Malzemeleri, **₺41,400** in total, due in 30 days. It is waiting for your approval on the card below.',
    reason: 'Invoice requested for 12 pallets of cement at ₺3,450 each.',
    line: 'Cement, pallet',
    renamed: ['CEM-25 — Cement 25 kg', 'CEM-25 — Cement 25 kg (grey)'],
    leave: 'Can Yıldız, annual leave 20–24 Oct',
    rent: 'JE#342 2026-10-13 October rent',
    chat: 'Which customer invoices are overdue?',
  },
  tr: {
    user: 'Ayşe Demir',
    company: 'Demir Yapı Market A.Ş.',
    conversationTitle: 'Hangi satış faturalarının vadesi geçti?',
    otherConversations: ['Bu hafta bitecek stoklar', 'Ekim bordro maliyeti', 'Bu çeyreğin en büyük tedarikçileri'],
    q1: 'Hangi satış faturalarının vadesi geçti?',
    a1: 'Vadesi geçmiş üç satış faturası var; toplam **₺42.600**. En büyüğü 34 gündür geciken ₺21.400 tutarındaki Ege Lojistik faturası. Hepsi aşağıdaki tabloda.',
    t1: 'Vadesi geçmiş satış faturaları',
    q2: 'Bu yılın aylık gelirini grafikle göster',
    a2: 'Bu yıl gelir, **₺2.815.000** ile Eylül ayında en yüksek seviyeye ulaştı. Ekim ayı henüz tamamlanmadı. Aylar aşağıdaki grafikte.',
    t2: 'Aylık gelir, 2026',
    q3: 'Anadolu Yapı için fatura oluştur: 12 palet çimento, tanesi 3.450',
    a3: 'Anadolu Yapı Malzemeleri için toplam **₺41.400** tutarında, 30 gün vadeli faturayı hazırladım. Aşağıdaki kartta onayınızı bekliyor.',
    reason: 'Tanesi ₺3.450 olan 12 palet çimento için fatura istendi.',
    line: 'Çimento, palet',
    renamed: ['CEM-25 — Çimento 25 kg', 'CEM-25 — Çimento 25 kg (gri)'],
    leave: 'Can Yıldız, yıllık izin 20–24 Eki',
    rent: 'JE#342 2026-10-13 Ekim kirası',
    chat: 'Hangi satış faturalarının vadesi geçti?',
  },
}

function widgetData(key) {
  const stat = (value, extra = {}) => ({ kind: 'stat', value: String(value), format: 'money', secondary: [], delta: null, trend: [], route: null, ...extra })
  const net = REVENUE.map((revenue, i) => revenue - EXPENSES[i])
  const data = {
    cash_position: stat(1284500, { secondary: [{ key: 'change_this_month', value: '86200', format: 'money' }], trend: trend([905000, 962000, 1041000, 1118000, 1198300, 1284500]), route: '/trial-balance' }),
    revenue_mtd: stat(1643000, { delta: { percent: '-41.6', compare_key: 'vs_last_month', good_when: 'up' }, trend: trend(REVENUE.slice(-6)), route: '/trial-balance' }),
    expenses_mtd: stat(1182000, { delta: { percent: '-43.1', compare_key: 'vs_last_month', good_when: 'down' }, trend: trend(EXPENSES.slice(-6)), route: '/trial-balance' }),
    net_income_mtd: stat(461000, { delta: { percent: '-37.6', compare_key: 'vs_last_month', good_when: 'up' }, trend: trend(net.slice(-6)), route: '/trial-balance' }),
    ar_outstanding: stat(612400, { secondary: [{ key: 'overdue', value: '42600', format: 'money' }, { key: 'open_documents', value: '27', format: 'number' }], route: '/invoices' }),
    ap_outstanding: stat(388900, { secondary: [{ key: 'overdue', value: '0', format: 'money' }, { key: 'open_documents', value: '14', format: 'number' }], route: '/bills' }),
    open_sales_orders: stat(274300, { secondary: [{ key: 'open_orders', value: '18', format: 'number' }, { key: 'draft_orders', value: '5', format: 'number' }], route: '/sales-orders' }),
    open_purchase_orders: stat(196800, { secondary: [{ key: 'open_orders', value: '9', format: 'number' }, { key: 'draft_orders', value: '2', format: 'number' }], route: '/purchase-orders' }),
    stock_summary: stat(486, { format: 'number', secondary: [{ key: 'units_on_hand', value: '18240', format: 'number' }, { key: 'warehouses', value: '3', format: 'number' }], route: '/stock-levels' }),
    headcount: stat(42, { format: 'number', secondary: [{ key: 'monthly_gross_payroll', value: '1764000', format: 'money' }, { key: 'on_leave_today', value: '2', format: 'number' }], route: '/employees' }),
    pos_sales_today: stat(38450, {
      delta: { percent: '12.4', compare_key: 'vs_yesterday', good_when: 'up' },
      secondary: [{ key: 'transactions', value: '64', format: 'number' }, { key: 'open_shifts', value: '2', format: 'number' }],
      trend: points([['2026-10-07', 31200], ['2026-10-08', 29800], ['2026-10-09', 35400], ['2026-10-10', 41900], ['2026-10-11', 44300], ['2026-10-12', 34200], ['2026-10-13', 38450]]),
      route: '/pos/shifts',
    }),
    marketplace_orders: stat(137, {
      format: 'number',
      secondary: [{ key: 'failed_orders', value: '0', format: 'number' }, { key: 'unsynced_orders', value: '3', format: 'number' }],
      trend: points([['2026-10-07', 16], ['2026-10-08', 19], ['2026-10-09', 22], ['2026-10-10', 18], ['2026-10-11', 24], ['2026-10-12', 17], ['2026-10-13', 21]]),
      route: '/ecommerce/orders',
    }),
    attention: {
      kind: 'attention',
      items: [
        { key: 'overdue_invoices', count: 3, severity: 'critical', route: '/aging', amount: '42600' },
        { key: 'bills_due_soon', count: 2, severity: 'warning', route: '/bills', amount: '18400' },
        { key: 'low_stock', count: 4, severity: 'warning', route: '/stock-levels', amount: null },
        { key: 'purchase_orders_awaiting_approval', count: 1, severity: 'warning', route: '/purchase-orders', amount: null },
        { key: 'pending_leave_requests', count: 2, severity: 'warning', route: '/leave-requests', amount: null },
        { key: 'ai_pending_approvals', count: 1, severity: 'warning', route: '/assistant', amount: null },
      ],
    },
    revenue_expense_trend: {
      kind: 'chart', chart: 'line', format: 'money', label_kind: 'month', route: '/trial-balance',
      series: [{ key: 'revenue', points: trend(REVENUE, MONTHS) }, { key: 'expenses', points: trend(EXPENSES, MONTHS) }],
    },
    cash_forecast: {
      kind: 'chart', chart: 'bar', format: 'money', label_kind: 'date', route: '/aging',
      series: [
        { key: 'inflow', points: points([['overdue', 42600], ['2026-10-13', 188200], ['2026-10-20', 161500], ['2026-10-27', 137400], ['2026-11-03', 82700]]) },
        { key: 'outflow', points: points([['overdue', 0], ['2026-10-13', 94100], ['2026-10-20', 129900], ['2026-10-27', 76200], ['2026-11-03', 88700]]) },
      ],
    },
    ar_aging: {
      kind: 'chart', chart: 'bar', format: 'money', label_kind: 'key', route: '/aging',
      series: [{ key: 'balance', points: points([['current', 569800], ['d1_30', 21200], ['d31_60', 21400], ['d61_90', 0], ['d90_plus', 0]]) }],
    },
  }
  return data[key] ? { key, ...data[key] } : null
}

function conversation(text) {
  const proposal = {
    id: 512, action_name: 'invoice.create', resource: 'invoice', operation: 'create', target_id: '',
    action_input: { party: 'Anadolu Yapı Malzemeleri A.Ş.', issue_date: '2026-10-13', due_date: '2026-11-12', lines: [{ description: text.line, quantity: '12.00', unit_price: '3450.00' }] },
    preview: { target_label: '', reason: text.reason, changes: [] },
    summary: '', status: 'pending', can_approve: true, requested_by_username: 'ayse', resolved_by_username: null, result: null, error: '',
  }
  const message = (id, role, body, blocks = []) => ({ id, role, text: body, blocks, citations: [], created_at: '2026-10-13T09:40:00Z' })
  return {
    id: 101, title: text.conversationTitle, created_at: '2026-10-13T09:40:00Z', updated_at: '2026-10-13T09:44:00Z',
    messages: [
      message(1, 'user', text.q1),
      message(2, 'assistant', text.a1, [{
        type: 'table', title: text.t1, resource: 'invoice', columns: ['party', 'due_date', 'days_overdue', 'balance_due'], total: 3,
        rows: [
          { party: 'Ege Lojistik A.Ş.', due_date: '2026-09-09', days_overdue: 34, balance_due: '21400.00' },
          { party: 'Karadeniz Tekstil Ltd. Şti.', due_date: '2026-09-28', days_overdue: 15, balance_due: '13200.00' },
          { party: 'Marmara Gıda Ltd. Şti.', due_date: '2026-10-06', days_overdue: 7, balance_due: '8000.00' },
        ],
      }]),
      message(3, 'user', text.q2),
      message(4, 'assistant', text.a2, [{
        type: 'chart', title: text.t2, series_name: 'monthly_revenue', chart: 'line', format: 'money', label_kind: 'month',
        series: [{ name: 'monthly_revenue', points: trend(REVENUE.slice(2), MONTHS.slice(2)) }],
      }]),
      message(5, 'user', text.q3),
      message(6, 'assistant', text.a3, [{ type: 'proposal', approval: proposal }]),
    ],
  }
}

function auditLog(text) {
  const people = { ayse: { id: 2, username: 'ayse', full_name: 'Ayşe Demir' }, mehmet: { id: 3, username: 'mehmet', full_name: 'Mehmet Kaya' }, zeynep: { id: 4, username: 'zeynep', full_name: 'Zeynep Arslan' } }
  const can = { can_revert: true, reason: null }
  const entry = (id, time, user, channel, action, label, extra = {}) => {
    const [resource, operation] = action.split('.')
    return { id, created_at: `2026-10-13T${time}:00+03:00`, user: people[user], channel, action, resource, operation: operation || '', target_id: String(id), target_label: label, changes: [], before: null, after: null, reverts: null, reverted_by: null, revert: can, ...extra }
  }
  const renameChange = [{ field: 'name', before: text.renamed[0].split(' — ')[1], after: text.renamed[1].split(' — ')[1] }]
  return {
    count: 8, next: null, previous: null,
    results: [
      entry(418, '14:32', 'ayse', 'ai', 'invoice.create', 'INV-128 Anadolu Yapı Malzemeleri A.Ş.', { after: { id: 128 } }),
      entry(417, '14:10', 'mehmet', 'manual', 'item.update', text.renamed[1], { changes: renameChange, before: { name: renameChange[0].before }, after: { name: renameChange[0].after } }),
      entry(416, '13:45', 'mehmet', 'manual', 'purchase_order.approve', 'PO-57 Marmara Çelik San. A.Ş.'),
      entry(415, '13:20', 'ayse', 'manual', 'payment.create', 'Payment 21400.00 -> INV-119 Ege Lojistik A.Ş.'),
      entry(414, '12:05', 'zeynep', 'ai', 'leave_request.approve', text.leave),
      entry(413, '11:48', 'mehmet', 'manual', 'bill.send_document', 'BILL-73 Trakya Ambalaj Ltd. Şti.', { reverts: 409, revert: { can_revert: false, reason: 'is_a_revert' } }),
      entry(412, '10:15', 'zeynep', 'manual', 'journal_entry.post_entry', text.rent),
      entry(411, '09:40', 'ayse', 'ai', 'ai_chat', text.chat, { resource: 'conversation', operation: '', revert: { can_revert: false, reason: 'not_an_action' } }),
    ],
  }
}

async function capture(browser, locale) {
  const text = TEXT[locale]
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }])

  await page.goto(APP + '/login')
  await page.evaluate((l) => {
    localStorage.setItem('locale', l)
    localStorage.removeItem('sidebar-collapsed')
  }, locale)
  await page.goto(APP + '/login', { waitUntil: 'networkidle0' })
  await page.type('input[type="text"], input:not([type])', process.env.LANDING_USER || 'admin')
  await page.type('input[type="password"]', process.env.LANDING_PASSWORD || '')
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.keyboard.press('Enter')])

  // The real answers the sample data is layered over.
  const real = await page.evaluate(async () => {
    const get = (url) => fetch('/api/v1/' + url).then((r) => r.json())
    return { me: await get('core/auth/me/'), plugins: await get('plugins/'), widgets: await get('plugins/widgets/'), actions: await get('access/actions/') }
  })
  const allActions = real.actions.flatMap((group) => group.resources.flatMap((resource) => resource.operations.map((op) => op.code)))
  const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

  await page.setRequestInterception(true)
  page.on('request', (request) => {
    const url = new URL(request.url())
    const api = url.pathname.startsWith('/api/v1/') ? url.pathname.slice('/api/v1/'.length) : null
    if (api === null || request.method() !== 'GET') return request.continue()

    if (api === 'core/auth/me/') return request.respond(json({ ...real.me, full_name: text.user, access: { is_org_admin: true, actions: [...allActions, 'entity.view', 'user.view', 'role.view', 'permission.view'] } }))
    if (api === 'core/entities/') return request.respond(json({ count: 1, next: null, previous: null, results: [{ id: 1, name: text.company, code: 'DYM', currency: 'TRY', is_active: true }] }))
    if (api === 'plugins/') return request.respond(json({ can_manage: true, plugins: real.plugins.plugins.map((p) => ({ ...p, is_licensed: true, is_enabled: true, is_active: true })) }))
    if (api === 'plugins/widgets/') return request.respond(json(real.widgets.map((w) => ({ ...w, is_available: true }))))
    const widget = api.match(/^plugins\/widgets\/(\w+)\/data\/$/)
    if (widget && widgetData(widget[1])) return request.respond(json(widgetData(widget[1])))
    if (api === 'ai/conversations/') {
      const others = text.otherConversations.map((title, i) => ({ id: 90 - i, title, created_at: '2026-10-12T10:00:00Z', updated_at: `2026-10-1${2 - Math.min(i, 2)}T10:00:00Z` }))
      return request.respond(json([{ id: 101, title: text.conversationTitle, created_at: '2026-10-13T09:40:00Z', updated_at: '2026-10-13T09:44:00Z' }, ...others]))
    }
    if (api === 'ai/conversations/101/') return request.respond(json(conversation(text)))
    if (api === 'access/audit-log/') return request.respond(json(auditLog(text)))
    return request.continue()
  })

  const shoot = (name) => page.screenshot({ path: path.join(OUT, `${name}-${locale}.webp`), type: 'webp', quality: 84 })
  const open = async (route, width, height, collapsed) => {
    await page.setViewport({ width, height, deviceScaleFactor: 2 })
    await page.evaluate((c) => (c ? localStorage.setItem('sidebar-collapsed', 'true') : localStorage.removeItem('sidebar-collapsed')), collapsed)
    await page.goto(APP + route, { waitUntil: 'networkidle0' })
    await wait(1200)
  }

  await open('/panel', 1440, 900, false)
  await shoot('panel')

  await open('/assistant', 1000, 1300, true)
  await page.evaluate(() => document.querySelector('main aside ul li button')?.click())
  await wait(1500)
  await shoot('assistant')

  await open('/audit-log', 1180, 760, true)
  // Open the details of the entry that changed a field.
  await page.evaluate(() => document.querySelectorAll('main tbody button[aria-expanded]')[1]?.click())
  await wait(400)
  await shoot('audit')

  await open('/plugins', 1180, 760, true)
  await shoot('plugins')

  await page.close()
}

;(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new' })
  for (const locale of ['en', 'tr']) {
    // A context per language: the session and locale don't carry over.
    const context = await browser.createBrowserContext()
    await capture(context, locale)
    await context.close()
    console.log('captured', locale)
  }
  await browser.close()
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
