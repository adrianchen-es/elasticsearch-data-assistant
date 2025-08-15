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
import fs from 'fs';

const serviceName = process.env.OTEL_SERVICE_NAME || 'es-data-assistant-gateway';
const useGrpc = (process.env.OTEL_EXPORTER_OTLP_PROTOCOL || '').toLowerCase() === 'grpc';

// Enhanced resource detection with host and container metadata
const detectContainerInfo = () => {
  const containerInfo = {};
  
  try {
    // Docker container detection
    if (fs.existsSync('/.dockerenv')) {
      containerInfo['container.runtime'] = 'docker';
    }
    
    // Try to read container ID from cgroup
    try {
      const cgroupContent = fs.readFileSync('/proc/self/cgroup', 'utf8');
      const dockerMatch = cgroupContent.match(/\/docker\/([a-f0-9]{64})/);
      if (dockerMatch) {
        containerInfo['container.id'] = dockerMatch[1].substring(0, 12); // Short container ID
      }
    } catch (err) {
      // Ignore if can't read cgroup
    }
    
    // Kubernetes detection
    if (process.env.KUBERNETES_SERVICE_HOST) {
      containerInfo['k8s.cluster.name'] = process.env.K8S_CLUSTER_NAME || 'unknown';
      containerInfo['k8s.namespace.name'] = process.env.K8S_NAMESPACE || process.env.NAMESPACE || 'default';
      containerInfo['k8s.pod.name'] = process.env.K8S_POD_NAME || process.env.HOSTNAME;
      containerInfo['k8s.deployment.name'] = process.env.K8S_DEPLOYMENT_NAME;
      containerInfo['k8s.node.name'] = process.env.K8S_NODE_NAME;
    }
  } catch (err) {
    console.warn('Could not detect container info:', err.message);
  }
  
  return containerInfo;
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

// Set up metrics provider
const meterProvider = new MeterProvider({
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
  readers: [
    new PeriodicExportingMetricReader({
      exporter: metricExporter,
      exportIntervalMillis: 5000 // Export metrics every 5 seconds
    })
  ]
});

metrics.setGlobalMeterProvider(meterProvider);

export const sdk = new NodeSDK({
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

// Create custom metrics
const meter = metrics.getMeter('es-data-assistant-gateway', '1.0.0');

// System metrics
const cpuUsageGauge = meter.createObservableGauge('system.cpu.usage', {
  description: 'System CPU usage percentage'
});

const memoryUsageGauge = meter.createObservableGauge('system.memory.usage', {
  description: 'System memory usage in bytes'
});

const memoryUsagePercentGauge = meter.createObservableGauge('system.memory.usage.percent', {
  description: 'System memory usage percentage'
});

// Process metrics
const processMemoryGauge = meter.createObservableGauge('process.memory.usage', {
  description: 'Process memory usage in bytes'
});

const processUptimeGauge = meter.createObservableGauge('process.uptime', {
  description: 'Process uptime in seconds'
});

// Collect system metrics
let lastCpuInfo = os.cpus();
let lastMeasure = process.hrtime();

const collectSystemMetrics = () => {
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
  
  return {
    cpuUsage,
    usedMemory,
    memoryPercent,
    processMemory,
    uptime: process.uptime()
  };
};

// Register metric callbacks
cpuUsageGauge.addCallback((observableResult) => {
  const metrics = collectSystemMetrics();
  observableResult.observe(metrics.cpuUsage);
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
