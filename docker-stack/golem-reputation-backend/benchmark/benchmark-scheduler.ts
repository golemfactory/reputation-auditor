import { CronJob } from "cron";
import { endOfDay, format } from "date-fns";
import { createClient } from "redis";
import { program } from "commander";

// Store last run date in Redis

type RedisClientType = ReturnType<typeof createClient>;


let DEBUG = process.env.DEBUG === "true";
const REDIS_URL = process.env.REDIS_URL || "redis://redis:6379";
let REDIS_KEY = "benchmark-last-run";
let CRON_TIME = "0 0 * * *";

/**
 * Minimum amount of time before midnight in milliseconds that the scheduler should be executed.
 */
const executionThreshold = 1000 * 60 * 30; // 30 minutes

/**
 * Returns a random time to sleep before executing the code, however it no longer than midnight.
 *
 * Takes into account the `executionThreshold` to ensure that the code is executed and completed before midnight.
 */
function getSleepTime() {
  // Do not sleep if debugging.
  if (DEBUG) {
    return 0;
  }

  const now = new Date();
  const eod = endOfDay(now).getTime() - now.getTime() - executionThreshold;

  if (eod < 0) {
    return 0;
  }

  return eod * Math.random();
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Run benchmark script and pipe stdout and stderr to the console.
 */
function executeVmBenchmark(): Promise<void> {
  return executeBenchmarkerScript("npm", ["run", "benchmark", 2]);
}


/**
 * Run benchmark script and pipe stdout and stderr to the console.
 */
function executeVmNvidiaBenchmark(): Promise<void> {
  return executeBenchmarkerScript("npm", ["run", "gpu-benchmark", "--", "--count", "2"]);
}

/**
 * Run benchmark script and pipe stdout and stderr to the console.
 */
function executeBenchmarkerScript(command: string, args: any): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const { spawn } = require("child_process");
    const benchmark = spawn(command, args, {
      // pipe
      stdio: "inherit"
    });

    benchmark.on("exit", (code: number) => {
      if (code === 0) {
        console.log(`Benchmark process exited with code ${code}`);
        resolve();
      } else {
        console.log(`Benchmark process exited with non-zero code ${code}`);
        reject(new Error(`Benchmark process exited with non-zero code ${code}`));
      }
    });

    benchmark.on("error", (err: Error) => {
      console.error("Failed to start benchmark process.", err);
      reject(err);
    });
  });
}

async function setupRedis(): Promise<RedisClientType> {
  const redis = createClient({
    url: REDIS_URL,
  });

  redis.on("error", (err) => {
    console.error("Redis error:", err);
  });
  redis.on("ready", () => {
    console.log("Redis connected.");
  });
  redis.on("reconnecting", () => {
    console.log("Redis reconnecting.");
  });
  redis.on("disconnected", () => {
    console.log("Redis disconnected.");
  });

  await redis.connect();

  return redis;
}

async function wasRunToday(redis: RedisClientType) {
  const lastRun = await redis.get(REDIS_KEY);
  if (!lastRun) {
    return false;
  }

  const now = format(new Date(lastRun), "yyyy-MM-dd");
  return now === lastRun;
}

async function updateLastRun(redis: RedisClientType) {
  await redis.set(REDIS_KEY, format(new Date(), "yyyy-MM-dd"));
}

async function cronFunc(job: CronJob, redis: RedisClientType, benchmark: string) {
  job.stop();
  const sleepTimeMs = getSleepTime();
  const nextTime = new Date(Date.now() + sleepTimeMs);
  console.log("Random wait time added, waiting until ", nextTime);
  await delay(sleepTimeMs);
  let benchmarkName = benchmark;
  try {
    if (benchmark === 'all') {
      benchmarkName = 'vm';
      await executeVmBenchmark();
      benchmarkName = 'vm-nvidia';
      await executeVmNvidiaBenchmark();
    } else if (benchmark === 'vm-nvidia') {
        await executeVmNvidiaBenchmark();
    } else {
      await executeVmBenchmark();
    }

    await updateLastRun(redis);
    console.log("Benchmark executed successfully.");
  } catch (e) {
    console.log(`Benchmark ${benchmarkName} failed:`, e);
  }
  job.start();
  console.log(`Next job will start at ${job.nextDate()} + random delay`);
}

async function main(benchmark: string) {
  const redis = await setupRedis();

  console.log(`Benchmark cron for ${benchmark} started: ${CRON_TIME}`);
  const job = CronJob.from({
    cronTime: CRON_TIME,
    onTick: async () => {
      await cronFunc(job, redis, benchmark)
    },
    start: true,
    timeZone: "Europe/Warsaw"
  });

  const wasRun = await wasRunToday(redis);
  if (wasRun && !DEBUG) {
    console.log("Benchmark was already run today, skipping.");
    console.log(`Job will start at ${job.nextDate()} + random delay`);
  } else {
    console.log("Benchmark was not run today, executing now.");
    await cronFunc(job, redis, benchmark);
  }

}

program
  .option("-k, --redis-key <key>", "Redis key to store last run date.", REDIS_KEY)
  .option("-c, --cron-time <time>", "Cron time to run the benchmark.", CRON_TIME)
  .option("-b, --benchmark <name>", "Benchmark to run (all, vm or vm-nvidia).", "vm")
  .option('-d, --debug', "Debug mode. Run benchmark immediately and without random delay.", DEBUG)
  .action(async (options) => {
    REDIS_KEY = options.redisKey;
    CRON_TIME = options.cronTime;
    DEBUG = options.debug;

    await main(options.benchmark).catch((e) => {
      console.error("Benchmark scheduler failed:", e);
      process.exit(1);
    });
  });


program.parse(process.argv);