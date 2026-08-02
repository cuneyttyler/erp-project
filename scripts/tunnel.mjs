#!/usr/bin/env node
/**
 * Keep-alive wrapper around `cloudflared tunnel --url` (see Makefile's
 * `tunnel` target). Cloudflare's quick tunnels are far more reliable than
 * localtunnel's free relay (no more silently-dead "zombie" tunnels), but
 * the process can still exit (network blip, laptop sleep/wake, etc.), so
 * this restarts it automatically rather than leaving the app unreachable
 * until someone notices and reruns the command by hand.
 *
 * Quick tunnels get a fresh random *.trycloudflare.com hostname on every
 * start -- there's no fixed-name option without owning a domain in
 * Cloudflare and running a named tunnel instead. The assigned URL is
 * printed clearly on every (re)connect.
 */

import { spawn } from 'node:child_process'

const PORT = Number(process.env.TUNNEL_PORT || 5173)
const RESTART_DELAY_MS = Number(process.env.TUNNEL_RESTART_DELAY_MS || 3_000)

let closing = false

function log(...args) {
  console.log('[tunnel]', new Date().toISOString(), ...args)
}

function start() {
  if (closing) return
  log(`starting cloudflared quick tunnel for http://localhost:${PORT} ...`)
  const child = spawn('cloudflared', ['tunnel', '--url', `http://localhost:${PORT}`], {
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  let announced = false
  const onOutput = (data) => {
    const text = data.toString()
    process.stdout.write(text)
    if (!announced) {
      const match = text.match(/https:\/\/[a-zA-Z0-9-]+\.trycloudflare\.com/)
      if (match) {
        announced = true
        log(`tunnel URL: ${match[0]}`)
      }
    }
  }
  child.stdout.on('data', onOutput)
  child.stderr.on('data', onOutput)

  child.on('exit', (code, signal) => {
    log(`cloudflared exited (code=${code}, signal=${signal})`)
    if (!closing) {
      log(`restarting in ${RESTART_DELAY_MS}ms...`)
      setTimeout(start, RESTART_DELAY_MS)
    }
  })
  child.on('error', (err) => {
    log('failed to launch cloudflared:', err.message)
    if (!closing) setTimeout(start, RESTART_DELAY_MS)
  })
}

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    closing = true
    process.exit(0)
  })
}

start()
