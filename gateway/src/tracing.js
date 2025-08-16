import 'dotenv/config';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { Resource } from '@opentelemetry/resources';
import * as SemanticConventions from '@opentelemetry/semantic-conventions';
// Support multiple OpenTelemetry package versions: prefer SemanticResourceAttributes,
// fall back to ResourceAttributes (older versions) if available.
const SemanticResourceAttributes = SemanticConventions.SemanticResourceAttributes || SemanticConventions.ResourceAttributes || {};
import { OTLPTraceExporter as OTLPHttpExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPTraceExporter as OTLPGrpcExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { metrics } from '@opentelemetry/api';
import os from 'os';
import * as fs from 'fs';

const serviceName = process.env.OTEL_SERVICE_NAME || 'es-data-assistant-gateway';
const useGrpc = (process.env.OTEL_EXPORTER_OTLP_PROTOCOL || '').toLowerCase() === 'grpc';

// Enhanced resource detection with host and container metadata
export const detectContainerInfo = () => {
  const containerInfo = {};
  
  try {
    // Prefer Kubernetes detection when env var present
    if (process.env.KUBERNETES_SERVICE_HOST) {
      containerInfo['k8s.cluster.name'] = process.env.K8S_CLUSTER_NAME || process.env.CLUSTER_NAME || 'unknown';
      containerInfo['k8s.namespace.name'] = process.env.K8S_NAMESPACE || process.env.POD_NAMESPACE || process.env.NAMESPACE || 'default';
      containerInfo['k8s.pod.name'] = process.env.K8S_POD_NAME || process.env.POD_NAME || process.env.HOSTNAME;
      containerInfo['k8s.deployment.name'] = process.env.K8S_DEPLOYMENT_NAME || process.env.DEPLOYMENT_NAME;
      containerInfo['k8s.node.name'] = process.env.K8S_NODE_NAME || process.env.NODE_NAME;
      // mark runtime as kubernetes explicitly
      containerInfo['container.runtime'] = containerInfo['container.runtime'] || 'kubernetes';
    }

    // Try to read container ID and runtime hints from cgroup first
    try {
      if (fs.existsSync('/proc/self/cgroup')) {
        const cgroupContent = fs.readFileSync('/proc/self/cgroup', 'utf8');
        const dockerMatch = cgroupContent.match(/\/docker\/([a-f0-9A-F]+)/i);
        if (dockerMatch) {
          containerInfo['container.id'] = dockerMatch[1].substring(0, 12); // Short container ID
          containerInfo['container.runtime'] = containerInfo['container.runtime'] || 'docker';
        } else {
          // fallback: try to find any hex-like id in the cgroup line
          const fallback = cgroupContent.match(/([0-9a-fA-F]{6,})/);
          if (fallback) {
            containerInfo['container.id'] = fallback[1].substring(0, 12);
          }
        }
        // detect kubepods presence
        if (cgroupContent.includes('kubepods')) {
          containerInfo['container.runtime'] = containerInfo['container.runtime'] || 'kubernetes';
        }
      }
    } catch (err) {
      // Ignore if can't read cgroup
    }

    // Docker detection fallback (when not determined by cgroup/k8s)
    try {
      if (!containerInfo['container.runtime'] && fs.existsSync('/.dockerenv')) {
        containerInfo['container.runtime'] = 'docker';
      }
    } catch (err) {
      // ignore
    }
  } catch (err) {
    console.warn('Could not detect container info:', err.message);
  }
  
    // Normalize into a friendly shape expected by tests
    const normalized = {
      isContainer: !!(containerInfo['container.runtime'] || containerInfo['k8s.pod.name']),
      // Use explicit runtime value if provided, otherwise infer
      runtime: containerInfo['container.runtime'] || (containerInfo['k8s.pod.name'] ? 'kubernetes' : 'host'),
      id: containerInfo['container.id'] ? String(containerInfo['container.id']) : null,
      podName: containerInfo['k8s.pod.name'] || null,
      namespace: containerInfo['k8s.namespace.name'] || null,
      // keep raw keys for backward compatibility
      raw: containerInfo
    };

    if (process.env.NODE_ENV === 'test') {
      try {
        const dbg = {
          containerInfo,
        };
        // eslint-disable-next-line no-console
        try {
          dbg.exists_proc = typeof fs.existsSync === 'function' ? fs.existsSync('/proc/self/cgroup') : 'no-fn';
        } catch (e) { dbg.exists_proc = 'err'; }
        try {
          dbg.exists_docker = typeof fs.existsSync === 'function' ? fs.existsSync('/.dockerenv') : 'no-fn';
        } catch (e) { dbg.exists_docker = 'err'; }
        try {
          dbg.proc_content = (typeof fs.readFileSync === 'function' && dbg.exists_proc) ? fs.readFileSync('/proc/self/cgroup', 'utf8') : null;
        } catch (e) { dbg.proc_content = 'err'; }
        console.error('DEBUG detectContainerInfo:', JSON.stringify(dbg));
      } catch (e) {}
    }

    return normalized;
};

const httpExporter = new OTLPHttpExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://otel-collector:4318/v1/traces'
});
const grpcExporter = new OTLPGrpcExporter({
  url: process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || 'http://otel-collector:4317'
});

// Metrics exporter
const metricExporter = new OTLPMetricExporter({
  url: process.env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT || 'http://otel-collector:4318/v1/metrics'
});

// Metrics provider will be created during initTracing to avoid side-effects at import time
let meterProvider;
let meter;
let cpuUsageGauge;
let memoryUsageGauge;
let memoryUsagePercentGauge;
let processMemoryGauge;
let processUptimeGauge;

export let sdk;

export async function initTracing() {
  if (sdk) return sdk; // already initialized

  sdk = new NodeSDK({
    resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
    [SemanticResourceAttributes.SERVICE_VERSION]: process.env.SERVICE_VERSION || '1.0.0',
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
    [SemanticResourceAttributes.HOST_NAME]: os.hostname(),
    [SemanticResourceAttributes.HOST_ARCH]: os.arch(),
    [SemanticResourceAttributes.OS_TYPE]: os.type(),
    [SemanticResourceAttributes.OS_VERSION]: os.release(),
    [SemanticResourceAttributes.PROCESS_PID]: process.pid.toString(),
    [SemanticResourceAttributes.PROCESS_RUNTIME_NAME]: 'nodejs',
    [SemanticResourceAttributes.PROCESS_RUNTIME_VERSION]: process.version,
    ...detectContainerInfo()
  }),
  traceExporter: useGrpc ? grpcExporter : httpExporter,
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': {
      enabled: false // Disable filesystem instrumentation to reduce noise
    }
  })]
  });

  try {
    await sdk.start();
    console.log(`Gateway tracing initialized for service: ${serviceName}`);
    console.log(`Metrics collection enabled, exporting every 5 seconds`);
    console.log(`Host: ${os.hostname()}, Platform: ${os.type()} ${os.release()}`);

    // Set up metrics provider now that environment detection can run under test control
    meterProvider = new MeterProvider({
      resource: createServiceResource(),
      readers: [
        new PeriodicExportingMetricReader({
          exporter: metricExporter,
          exportIntervalMillis: 5000
        })
      ]
    });
    metrics.setGlobalMeterProvider(meterProvider);

    // Create meter and observable gauges
    meter = metrics.getMeter('es-data-assistant-gateway', '1.0.0');

    cpuUsageGauge = meter.createObservableGauge('system.cpu.usage', { description: 'System CPU usage percentage' });
    memoryUsageGauge = meter.createObservableGauge('system.memory.usage', { description: 'System memory usage in bytes' });
    memoryUsagePercentGauge = meter.createObservableGauge('system.memory.usage.percent', { description: 'System memory usage percentage' });
    processMemoryGauge = meter.createObservableGauge('process.memory.usage', { description: 'Process memory usage in bytes' });
    processUptimeGauge = meter.createObservableGauge('process.uptime', { description: 'Process uptime in seconds' });

    // Register metric callbacks
    cpuUsageGauge.addCallback((observableResult) => {
      const m = collectSystemMetrics();
      if (m && m.cpu) observableResult.observe(m.cpu.usage);
    });

    memoryUsageGauge.addCallback((observableResult) => {
      const m = collectSystemMetrics();
      if (m && m.memory) observableResult.observe(m.memory.used);
    });

    memoryUsagePercentGauge.addCallback((observableResult) => {
      const m = collectSystemMetrics();
      if (m && m.memory) observableResult.observe(m.memory.percent);
    });

    processMemoryGauge.addCallback((observableResult) => {
      const m = collectSystemMetrics();
      if (m && m.process) {
        observableResult.observe(m.process.rss, { type: 'rss' });
        observableResult.observe(m.process.heapUsed, { type: 'heap_used' });
        observableResult.observe(m.process.heapTotal, { type: 'heap_total' });
        observableResult.observe(m.process.external, { type: 'external' });
      }
    });

    processUptimeGauge.addCallback((observableResult) => {
      const m = collectSystemMetrics();
      if (m) observableResult.observe(m.uptime);
    });

  } catch (err) {
    console.error('Failed to start tracing SDK:', err && err.message ? err.message : err);
  }

  // Graceful shutdown wired when tracing is initialized
  const shutdown = async () => {
    try {
      await Promise.all([
        sdk && typeof sdk.shutdown === 'function' ? sdk.shutdown() : Promise.resolve(),
        meterProvider && typeof meterProvider.shutdown === 'function' ? meterProvider.shutdown() : Promise.resolve()
      ]);
      console.log('Tracing and metrics SDK shut down successfully');
    } catch (error) {
      console.error('Error shutting down SDK:', error);
    }
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  return sdk;
}

// Collect system metrics (shared implementation used by initTracing)
let lastCpuInfo = os.cpus();
let lastMeasure = process.hrtime();

export const collectSystemMetrics = () => {
  // CPU Usage calculation
  const currentCpuInfo = os.cpus();
  const currentMeasure = process.hrtime();
  
  let totalIdle = 0;
  let totalTick = 0;
  
  for (let i = 0; i < currentCpuInfo.length; i++) {
    const cpu = currentCpuInfo[i];
    const lastCpu = lastCpuInfo[i] || { times: { idle: 0, irq: 0, nice: 0, sys: 0, user: 0 } };
    
    const idle = cpu.times.idle - lastCpu.times.idle;
    const total = Object.values(cpu.times).reduce((acc, time) => acc + time, 0) - 
                  Object.values(lastCpu.times).reduce((acc, time) => acc + time, 0);
    
    totalIdle += idle;
    totalTick += total;
  }
  
  const cpuUsage = totalTick > 0 ? ((totalTick - totalIdle) / totalTick) * 100 : 0;
  
  lastCpuInfo = currentCpuInfo;
  lastMeasure = currentMeasure;
  
  // Memory usage
  const totalMemory = os.totalmem();
  const freeMemory = os.freemem();
  const usedMemory = totalMemory - freeMemory;
  const memoryPercent = (usedMemory / totalMemory) * 100;
  
  // Process memory
  const processMemory = process.memoryUsage();
  
    // Provide both compact and detailed shapes for tests
    return {
      cpu: {
        count: currentCpuInfo.length,
        usage: cpuUsage
      },
      memory: {
        total: totalMemory,
        free: freeMemory,
        used: usedMemory,
        percent: memoryPercent
      },
      process: {
        rss: processMemory.rss,
        heapUsed: processMemory.heapUsed,
        heapTotal: processMemory.heapTotal,
        external: processMemory.external
      },
      uptime: process.uptime()
  };
};

// Helper to create the service resource for tests
export const createServiceResource = () => new Resource({
  [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
  [SemanticResourceAttributes.SERVICE_VERSION]: process.env.SERVICE_VERSION || '1.0.0',
  [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
  [SemanticResourceAttributes.HOST_NAME]: os.hostname(),
  [SemanticResourceAttributes.HOST_ARCH]: os.arch(),
  [SemanticResourceAttributes.OS_TYPE]: os.type(),
  [SemanticResourceAttributes.OS_VERSION]: os.release(),
  [SemanticResourceAttributes.PROCESS_PID]: process.pid.toString(),
  [SemanticResourceAttributes.PROCESS_RUNTIME_NAME]: 'nodejs',
  [SemanticResourceAttributes.PROCESS_RUNTIME_VERSION]: process.version,
  ...detectContainerInfo()
});

memoryUsageGauge.addCallback((observableResult) => {
  const metrics = collectSystemMetrics();
  observableResult.observe(metrics.usedMemory);
});

memoryUsagePercentGauge.addCallback((observableResult) => {
  const metrics = collectSystemMetrics();
  observableResult.observe(metrics.memoryPercent);
});

processMemoryGauge.addCallback((observableResult) => {
  const metrics = collectSystemMetrics();
  observableResult.observe(metrics.processMemory.rss, { type: 'rss' });
  observableResult.observe(metrics.processMemory.heapUsed, { type: 'heap_used' });
  observableResult.observe(metrics.processMemory.heapTotal, { type: 'heap_total' });
  observableResult.observe(metrics.processMemory.external, { type: 'external' });
});

processUptimeGauge.addCallback((observableResult) => {
  const metrics = collectSystemMetrics();
  observableResult.observe(metrics.uptime);
});

// Start the SDK
sdk.start()

console.log(`Gateway tracing initialized for service: ${serviceName}`);
console.log(`Metrics collection enabled, exporting every 5 seconds`);
console.log(`Host: ${os.hostname()}, Platform: ${os.type()} ${os.release()}`);

// Graceful shutdown
const shutdown = async () => {
  try {
    await Promise.all([
      sdk.shutdown(),
      meterProvider.shutdown()
    ]);
    console.log('Tracing and metrics SDK shut down successfully');
  } catch (error) {
    console.error('Error shutting down SDK:', error);
  }
  process.exit(0);
};

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
