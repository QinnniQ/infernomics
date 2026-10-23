import rawCatalog from '../data/model-catalog.v2.json'
import rawArchive from '../data/benchmark.json'
import rawV1 from '../data/local-benchmark.json'
import rawV2 from '../data/local-v2-benchmark.json'
import { validateCatalog } from './catalog'
import { validateBenchmark } from './benchmark'
import { validateLocal } from './local'

export const catalog = validateCatalog(rawCatalog)
export const archive = validateBenchmark(rawArchive)
export const localV1 = validateLocal(rawV1)
export const localV2 = validateLocal(rawV2)
