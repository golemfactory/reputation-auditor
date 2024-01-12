export interface IThreadResult {
    arg: number;
    result: number;
    timeMs: number;
  }
  
  export interface IValidationTaskResult {
    system: {
      cpuCount: number;
      threadCount: number;
      memBytesTotal: number;
      memBytesFree: number;
    };
    results: IThreadResult[];
  }
  
  export interface IDurationInfo {
    min: number;
    max: number;
    avg: number;
  }
  
  export class Result {
    constructor(public readonly raw: IValidationTaskResult) {}
  
    public getConcurrency(): number {
      return this.raw.results.length;
    }
  
    public getValue(): number {
      const set = new Set(this.raw.results.map((r) => r.result));
  
      if (set.size !== 1) {
        throw new Error("Not all computed values are the same");
      }
  
      return Array.from(set)[0];
    }
  
    public getDuration(): IDurationInfo {
      const timings = this.raw.results.map((r) => r.timeMs);
  
      const min = Math.min(...timings);
      const max = Math.max(...timings);
  
      const sum = timings.reduce((acc, cur) => acc + cur, 0);
      const avg = sum / timings.length;
  
      return {
        min,
        max,
        avg,
      };
    }
  }