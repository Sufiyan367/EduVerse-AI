import { cpSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(frontend, 'dist')
const target = resolve(frontend, '../backend/quicklearn/static')
if (!existsSync(resolve(dist, 'index.html'))) throw new Error('Build the frontend before copying assets.')
mkdirSync(target, { recursive: true })
cpSync(dist, target, { recursive: true })
console.log(`Built frontend copied to ${target}`)
