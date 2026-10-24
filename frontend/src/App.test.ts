import { describe, it, expect } from 'vitest';
import { api } from './api';

describe('DataTrust AI Frontend API Client & Contract', () => {
  it('exposes all required backend methods including Phase 2 endpoints', () => {
    expect(typeof api.getHealth).toBe('function');
    expect(typeof api.getSources).toBe('function');
    expect(typeof api.getSchema).toBe('function');
    expect(typeof api.getSqlHistory).toBe('function');
    expect(typeof api.validateSql).toBe('function');
    expect(typeof api.executeSql).toBe('function');
    expect(typeof api.ask).toBe('function');
    expect(typeof api.getGraph).toBe('function');
    expect(typeof api.getEntityDetail).toBe('function');
    expect(typeof api.getNeighbors).toBe('function');
    expect(typeof api.findPaths).toBe('function');
    expect(typeof api.ingestDocument).toBe('function');
    expect(typeof api.ingestDocuments).toBe('function');
    expect(typeof api.getDocuments).toBe('function');
    expect(typeof api.getDocument).toBe('function');
    expect(typeof api.updateDocument).toBe('function');
    expect(typeof api.deleteDocument).toBe('function');
    expect(typeof api.getDocumentStats).toBe('function');
    expect(typeof api.getCommunities).toBe('function');
    expect(typeof api.getCommunityDetail).toBe('function');
    expect(typeof api.resolveEntities).toBe('function');
    expect(typeof api.inspectRouting).toBe('function');
    expect(typeof api.searchRetrieval).toBe('function');
    expect(typeof api.getEvaluations).toBe('function');
    expect(typeof api.runEvaluation).toBe('function');
    expect(typeof api.addCompany).toBe('function');
    expect(typeof api.addRelationship).toBe('function');
    expect(typeof api.resetData).toBe('function');
  });
});
