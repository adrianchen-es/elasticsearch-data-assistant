import { describe, it, expect } from 'vitest';
import QueryEditor from '../components/QueryEditor';
import MappingDisplay from '../components/MappingDisplay';
import { ProviderSelector, IndexSelector, TierSelector } from '../components/Selectors';

describe('component imports', () => {
  it('imports QueryEditor, MappingDisplay, Selectors without runtime errors', () => {
    expect(typeof QueryEditor).toBe('function');
    expect(typeof MappingDisplay).toBe('function');
    expect(typeof ProviderSelector).toBe('function');
    expect(typeof IndexSelector).toBe('function');
    expect(typeof TierSelector).toBe('function');
  });
});
