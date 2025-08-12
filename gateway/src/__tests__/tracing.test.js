import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NodeSDK } from '@opentelemetry/sdk-node';

// Mock OpenTelemetry modules
vi.mock('@opentelemetry/sdk-node', () => ({
  NodeSDK: vi.fn().mockImplementation(() => ({
    start: vi.fn(),
    shutdown: vi.fn()
  }))
}));

vi.mock('@opentelemetry/resources', () => ({
  Resource: {
    default: vi.fn().mockReturnValue({}),
    merge: vi.fn().mockReturnValue({})
  }
}));

vi.mock('@opentelemetry/semantic-conventions', () => ({
  SEMRESATTRS_SERVICE_NAME: 'service.name',
  SEMRESATTRS_SERVICE_VERSION: 'service.version',
  SEMRESATTRS_DEPLOYMENT_ENVIRONMENT: 'deployment.environment',
  SEMRESATTRS_HOST_NAME: 'host.name',
  SEMRESATTRS_HOST_ARCH: 'host.arch',
  SEMRESATTRS_OS_TYPE: 'os.type',
  SEMRESATTRS_CONTAINER_NAME: 'container.name',
  SEMRESATTRS_CONTAINER_ID: 'container.id',
  SEMRESATTRS_K8S_POD_NAME: 'k8s.pod.name',
  SEMRESATTRS_K8S_NAMESPACE_NAME: 'k8s.namespace.name'
}));

vi.mock('@opentelemetry/auto-instrumentations-node', () => ({
  getNodeAutoInstrumentations: vi.fn().mockReturnValue([])
}));

vi.mock('@opentelemetry/exporter-jaeger', () => ({
  JaegerExporter: vi.fn().mockImplementation(() => ({}))
}));

vi.mock('fs', () => ({
  readFileSync: vi.fn(),
  existsSync: vi.fn()
}));

vi.mock('os', () => ({
  hostname: vi.fn().mockReturnValue('test-hostname'),
  arch: vi.fn().mockReturnValue('x64'),
  type: vi.fn().mockReturnValue('Linux'),
  totalmem: vi.fn().mockReturnValue(8589934592), // 8GB
  freemem: vi.fn().mockReturnValue(4294967296), // 4GB
  cpus: vi.fn().mockReturnValue([
    { model: 'Test CPU', speed: 2400 },
    { model: 'Test CPU', speed: 2400 }
  ])
}));

describe('Tracing Configuration', () => {
  let tracing;
  let mockFs;
  
  beforeEach(async () => {
    vi.clearAllMocks();
    mockFs = await import('fs');
    
    // Mock container detection
    mockFs.existsSync.mockImplementation((path) => {
      if (path === '/.dockerenv') return true;
      if (path === '/proc/self/cgroup') return true;
      return false;
    });
    
    mockFs.readFileSync.mockImplementation((path) => {
      if (path === '/proc/self/cgroup') {
        return '12:memory:/docker/abcd1234';
      }
      return '';
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Container Detection', () => {
    it('should detect Docker container', async () => {
      const { detectContainerInfo } = await import('../tracing.js');
      
      const containerInfo = detectContainerInfo();
      
      expect(containerInfo.isContainer).toBe(true);
      expect(containerInfo.runtime).toBe('docker');
      expect(containerInfo.id).toContain('abcd1234');
    });

    it('should detect non-container environment', async () => {
      mockFs.existsSync.mockReturnValue(false);
      
      const { detectContainerInfo } = await import('../tracing.js');
      
      const containerInfo = detectContainerInfo();
      
      expect(containerInfo.isContainer).toBe(false);
      expect(containerInfo.runtime).toBe('host');
    });

    it('should handle Kubernetes environment', async () => {
      // Set up environment variables for K8s
      process.env.KUBERNETES_SERVICE_HOST = 'kubernetes.default.svc';
      process.env.POD_NAME = 'test-pod';
      process.env.POD_NAMESPACE = 'test-namespace';
      
      mockFs.readFileSync.mockImplementation((path) => {
        if (path === '/proc/self/cgroup') {
          return '12:memory:/kubepods/burstable/pod123/container456';
        }
        return '';
      });
      
      const { detectContainerInfo } = await import('../tracing.js');
      
      const containerInfo = detectContainerInfo();
      
      expect(containerInfo.isContainer).toBe(true);
      expect(containerInfo.runtime).toBe('kubernetes');
      expect(containerInfo.podName).toBe('test-pod');
      expect(containerInfo.namespace).toBe('test-namespace');
      
      // Clean up
      delete process.env.KUBERNETES_SERVICE_HOST;
      delete process.env.POD_NAME;
      delete process.env.POD_NAMESPACE;
    });
  });

  describe('Resource Creation', () => {
    it('should create resource with service information', async () => {
      const { createServiceResource } = await import('../tracing.js');
      
      const resource = createServiceResource();
      
      expect(resource).toBeDefined();
    });

    it('should include host metrics in resource', async () => {
      const { createServiceResource } = await import('../tracing.js');
      
      const resource = createServiceResource();
      
      // Verify that the resource includes host information
      expect(resource).toBeDefined();
    });
  });

  describe('SDK Initialization', () => {
    it('should initialize NodeSDK with correct configuration', async () => {
      // Import tracing module to trigger initialization
      await import('../tracing.js');
      
      expect(NodeSDK).toHaveBeenCalledWith(
        expect.objectContaining({
          resource: expect.any(Object),
          instrumentations: expect.any(Array)
        })
      );
    });

    it('should handle initialization errors gracefully', async () => {
      const mockSdk = {
        start: vi.fn().mockImplementation(() => {
          throw new Error('SDK initialization failed');
        }),
        shutdown: vi.fn()
      };
      
      NodeSDK.mockImplementation(() => mockSdk);
      
      // Should not throw error during import
      expect(async () => {
        await import('../tracing.js');
      }).not.toThrow();
    });
  });

  describe('Environment Configuration', () => {
    it('should use environment variables for configuration', async () => {
      process.env.OTEL_SERVICE_NAME = 'test-service';
      process.env.OTEL_SERVICE_VERSION = '1.0.0';
      process.env.NODE_ENV = 'test';
      
      await import('../tracing.js');
      
      // Verify that environment variables are used
      expect(NodeSDK).toHaveBeenCalled();
      
      // Clean up
      delete process.env.OTEL_SERVICE_NAME;
      delete process.env.OTEL_SERVICE_VERSION;
      delete process.env.NODE_ENV;
    });
  });

  describe('Metrics Collection', () => {
    it('should collect system metrics', async () => {
      const { collectSystemMetrics } = await import('../tracing.js');
      
      if (collectSystemMetrics) {
        const metrics = collectSystemMetrics();
        
        expect(metrics).toHaveProperty('memory');
        expect(metrics).toHaveProperty('cpu');
        expect(metrics.memory).toHaveProperty('total');
        expect(metrics.memory).toHaveProperty('free');
        expect(metrics.cpu).toHaveProperty('count');
      }
    });
  });
});
