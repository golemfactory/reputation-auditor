export enum AllowDeny {
  ALLOW= 'allow',
  DENY = 'deny',
}

export interface VmNvidiaBenchmarkRunnerOptions {
  providerList: string[];
  allowDeny: AllowDeny;

  dryRun: boolean;
  dryRunDuration: number;

  maxRuns: number
}
