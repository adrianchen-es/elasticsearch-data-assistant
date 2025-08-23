import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatInterface from '../ChatInterface';

describe('ChatInterface - Import Test', () => {
  it('should import ChatInterface successfully', () => {
    expect(ChatInterface).toBeDefined();
  });
});
