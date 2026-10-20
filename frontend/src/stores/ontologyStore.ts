import { create } from 'zustand';
import type {
  OntologyObject,
  OntologyLink,
  CompanyObject,
  PortfolioObject,
  SECFilingObject,
  OptionContractObject,
  ObjectType,
  LinkType,
  OntologyViewState,
} from '@/types/ontology';

interface OntologyStore {
  // Data
  objects: Map<string, OntologyObject>;
  links: OntologyLink[];

  // View state
  viewState: OntologyViewState;

  // Actions
  addObject: (object: OntologyObject) => void;
  removeObject: (id: string) => void;
  updateObject: (id: string, updates: Partial<OntologyObject>) => void;
  getObject: (id: string) => OntologyObject | undefined;
  getObjectsByType: (type: ObjectType) => OntologyObject[];

  addLink: (link: OntologyLink) => void;
  removeLink: (id: string) => void;
  getLinksForObject: (objectId: string) => OntologyLink[];
  getLinkedObjects: (objectId: string, linkType?: LinkType) => OntologyObject[];

  setSelectedObject: (id: string | null, type: ObjectType | null) => void;
  setObjectTypeFilters: (types: ObjectType[]) => void;
  setSearchQuery: (query: string) => void;
  setViewMode: (mode: 'graph' | 'list' | 'table') => void;
  toggleDetailPanel: () => void;
}

// ===== MOCK DATA =====

const mockCompanies: CompanyObject[] = [
  {
    id: 'company-aapl',
    type: 'company',
    ticker: 'AAPL',
    name: 'Apple Inc.',
    exchange: 'NASDAQ',
    sector: 'Technology',
    industry: 'Consumer Electronics',
    price: 178.45,
    marketCap: 2780000000000,
    volume: 54320000,
    change: 1.23,
    changeAmount: 2.17,
    fundamentals: {
      pe_ratio: 29.34,
      eps: 6.08,
      revenue: 383285000000,
      ebitda: 123140000000,
      profit_margin: 0.2531,
      roe: 1.4739,
      debt_to_equity: 1.96,
    },
    valuation: {
      ev_to_ebitda: 22.8,
      price_to_sales: 7.26,
      price_to_book: 43.65,
      peg_ratio: 2.43,
      dividend_yield: 0.0052,
    },
    technical: {
      rsi: 58.4,
      macd: 1.23,
      sma_50: 175.32,
      sma_200: 168.94,
      beta: 1.24,
    },
    description: 'Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide.',
    website: 'https://www.apple.com',
    logo_url: 'https://logo.clearbit.com/apple.com',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'company-msft',
    type: 'company',
    ticker: 'MSFT',
    name: 'Microsoft Corporation',
    exchange: 'NASDAQ',
    sector: 'Technology',
    industry: 'Software',
    price: 378.91,
    marketCap: 2820000000000,
    volume: 23140000,
    change: 0.87,
    changeAmount: 3.27,
    fundamentals: {
      pe_ratio: 35.42,
      eps: 10.70,
      revenue: 211915000000,
      ebitda: 98024000000,
      profit_margin: 0.3612,
      roe: 0.4243,
      debt_to_equity: 0.39,
    },
    valuation: {
      ev_to_ebitda: 28.1,
      price_to_sales: 13.32,
      price_to_book: 13.96,
      peg_ratio: 2.58,
      dividend_yield: 0.0075,
    },
    technical: {
      rsi: 62.1,
      macd: 2.47,
      sma_50: 368.45,
      sma_200: 342.17,
      beta: 0.89,
    },
    description: 'Microsoft Corporation develops, licenses, and supports software, services, devices, and solutions worldwide.',
    website: 'https://www.microsoft.com',
    logo_url: 'https://logo.clearbit.com/microsoft.com',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'company-googl',
    type: 'company',
    ticker: 'GOOGL',
    name: 'Alphabet Inc.',
    exchange: 'NASDAQ',
    sector: 'Technology',
    industry: 'Internet Services',
    price: 140.23,
    marketCap: 1750000000000,
    volume: 31240000,
    change: -0.34,
    changeAmount: -0.48,
    fundamentals: {
      pe_ratio: 26.84,
      eps: 5.22,
      revenue: 307394000000,
      ebitda: 92435000000,
      profit_margin: 0.2369,
      roe: 0.2741,
      debt_to_equity: 0.11,
    },
    valuation: {
      ev_to_ebitda: 18.9,
      price_to_sales: 5.69,
      price_to_book: 6.51,
      peg_ratio: 1.89,
      dividend_yield: 0.0000,
    },
    technical: {
      rsi: 54.8,
      macd: 0.89,
      sma_50: 138.67,
      sma_200: 131.42,
      beta: 1.05,
    },
    description: 'Alphabet Inc. offers various products and services including Google Search, ads, Android, Chrome, and YouTube.',
    website: 'https://www.abc.xyz',
    logo_url: 'https://logo.clearbit.com/google.com',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'company-tsla',
    type: 'company',
    ticker: 'TSLA',
    name: 'Tesla, Inc.',
    exchange: 'NASDAQ',
    sector: 'Automotive',
    industry: 'Electric Vehicles',
    price: 238.72,
    marketCap: 758000000000,
    volume: 112450000,
    change: 3.45,
    changeAmount: 7.96,
    fundamentals: {
      pe_ratio: 73.48,
      eps: 3.25,
      revenue: 96773000000,
      ebitda: 13656000000,
      profit_margin: 0.1538,
      roe: 0.2847,
      debt_to_equity: 0.18,
    },
    valuation: {
      ev_to_ebitda: 55.6,
      price_to_sales: 7.83,
      price_to_book: 14.27,
      peg_ratio: 4.12,
      dividend_yield: 0.0000,
    },
    technical: {
      rsi: 67.2,
      macd: 4.53,
      sma_50: 215.38,
      sma_200: 198.64,
      beta: 2.01,
    },
    description: 'Tesla, Inc. designs, develops, manufactures, and sells electric vehicles and energy generation and storage systems.',
    website: 'https://www.tesla.com',
    logo_url: 'https://logo.clearbit.com/tesla.com',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockPortfolios: PortfolioObject[] = [
  {
    id: 'portfolio-tech',
    type: 'portfolio',
    name: 'Tech Growth Portfolio',
    description: 'High-growth technology stocks',
    total_value: 1250000,
    cash: 125000,
    invested: 1125000,
    risk_metrics: {
      var_95: -45000,
      cvar_95: -67500,
      sharpe_ratio: 1.85,
      volatility: 0.24,
      beta: 1.18,
    },
    returns: {
      day: 1.23,
      week: 2.45,
      month: 5.67,
      ytd: 18.42,
      all_time: 34.56,
    },
    created_at: new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date().toISOString(),
    position_count: 4,
  },
];

const mockFilings: SECFilingObject[] = [
  {
    id: 'filing-aapl-10k',
    type: 'sec_filing',
    ticker: 'AAPL',
    form_type: '10-K',
    filing_date: '2024-10-27',
    accepted_date: '2024-10-27T16:30:00Z',
    accession_number: '0000320193-24-000123',
    document_url: 'https://www.sec.gov/cgi-bin/browse-edgar',
    summary: 'Apple reports record fiscal year 2024 revenue of $383.3B, driven by iPhone and Services growth.',
    key_points: [
      'Total revenue increased 2.3% YoY',
      'Services revenue reached $85.2B',
      'iPhone revenue of $200.6B',
      'R&D expenses increased to $31.4B',
    ],
    created_at: new Date('2024-10-27').toISOString(),
  },
];

const mockOptions: OptionContractObject[] = [
  {
    id: 'option-aapl-call-180',
    type: 'option_contract',
    ticker: 'O:AAPL250117C00180000',
    underlying: 'AAPL',
    strike: 180.0,
    expiration: '2025-01-17',
    contract_type: 'call',
    bid: 12.40,
    ask: 12.60,
    last: 12.50,
    volume: 15420,
    open_interest: 89340,
    greeks: {
      delta: 0.5832,
      gamma: 0.0187,
      theta: -0.0845,
      vega: 0.3124,
      rho: 0.0542,
    },
    implied_volatility: 0.2847,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockLinks: OntologyLink[] = [
  {
    id: 'link-1',
    type: 'peer_of',
    from_id: 'company-aapl',
    from_type: 'company',
    to_id: 'company-msft',
    to_type: 'company',
    properties: { similarity_score: 0.85 },
    weight: 0.85,
    created_at: new Date().toISOString(),
  },
  {
    id: 'link-2',
    type: 'peer_of',
    from_id: 'company-aapl',
    from_type: 'company',
    to_id: 'company-googl',
    to_type: 'company',
    properties: { similarity_score: 0.78 },
    weight: 0.78,
    created_at: new Date().toISOString(),
  },
  {
    id: 'link-3',
    type: 'competes_with',
    from_id: 'company-aapl',
    from_type: 'company',
    to_id: 'company-msft',
    to_type: 'company',
    properties: { market: 'Personal Computing' },
    weight: 0.72,
    created_at: new Date().toISOString(),
  },
  {
    id: 'link-4',
    type: 'has_filing',
    from_id: 'company-aapl',
    from_type: 'company',
    to_id: 'filing-aapl-10k',
    to_type: 'sec_filing',
    created_at: new Date().toISOString(),
  },
  {
    id: 'link-5',
    type: 'has_options',
    from_id: 'company-aapl',
    from_type: 'company',
    to_id: 'option-aapl-call-180',
    to_type: 'option_contract',
    created_at: new Date().toISOString(),
  },
];

// ===== STORE =====

export const useOntologyStore = create<OntologyStore>((set, get) => {
  // Initialize with mock data
  const initialObjects = new Map<string, OntologyObject>();
  [...mockCompanies, ...mockPortfolios, ...mockFilings, ...mockOptions].forEach(obj => {
    initialObjects.set(obj.id, obj);
  });

  return {
    objects: initialObjects,
    links: mockLinks,

    viewState: {
      view_mode: 'graph',
      selected_object_id: null,
      selected_object_type: null,
      object_type_filters: [],
      search_query: '',
      graph_layout: 'force',
      show_links: [],
      detail_panel_open: false,
      action_panel_open: false,
    },

    // Object operations
    addObject: (object) => {
      set((state) => {
        const newObjects = new Map(state.objects);
        newObjects.set(object.id, object);
        return { objects: newObjects };
      });
    },

    removeObject: (id) => {
      set((state) => {
        const newObjects = new Map(state.objects);
        newObjects.delete(id);
        const newLinks = state.links.filter(
          (link) => link.from_id !== id && link.to_id !== id,
        );
        return { objects: newObjects, links: newLinks };
      });
    },

    updateObject: (id, updates) => {
      set((state) => {
        const newObjects = new Map(state.objects);
        const existing = newObjects.get(id);
        if (existing) {
          newObjects.set(id, { ...existing, ...updates } as OntologyObject);
        }
        return { objects: newObjects };
      });
    },

    getObject: (id) => {
      return get().objects.get(id);
    },

    getObjectsByType: (type) => {
      return Array.from(get().objects.values()).filter((obj) => obj.type === type);
    },

    // Link operations
    addLink: (link) => {
      set((state) => ({
        links: [...state.links, link],
      }));
    },

    removeLink: (id) => {
      set((state) => ({
        links: state.links.filter((link) => link.id !== id),
      }));
    },

    getLinksForObject: (objectId) => {
      return get().links.filter(
        (link) => link.from_id === objectId || link.to_id === objectId,
      );
    },

    getLinkedObjects: (objectId, linkType) => {
      const links = get().links.filter((link) => {
        const matchesType = linkType ? link.type === linkType : true;
        return matchesType && (link.from_id === objectId || link.to_id === objectId);
      });

      const linkedObjectIds = links.map((link) =>
        link.from_id === objectId ? link.to_id : link.from_id,
      );

      return linkedObjectIds
        .map((id) => get().objects.get(id))
        .filter((obj): obj is OntologyObject => obj !== undefined);
    },

    // View state
    setSelectedObject: (id, type) => {
      set((state) => ({
        viewState: {
          ...state.viewState,
          selected_object_id: id,
          selected_object_type: type,
          detail_panel_open: id !== null,
        },
      }));
    },

    setObjectTypeFilters: (types) => {
      set((state) => ({
        viewState: {
          ...state.viewState,
          object_type_filters: types,
        },
      }));
    },

    setSearchQuery: (query) => {
      set((state) => ({
        viewState: {
          ...state.viewState,
          search_query: query,
        },
      }));
    },

    setViewMode: (mode) => {
      set((state) => ({
        viewState: {
          ...state.viewState,
          view_mode: mode,
        },
      }));
    },

    toggleDetailPanel: () => {
      set((state) => ({
        viewState: {
          ...state.viewState,
          detail_panel_open: !state.viewState.detail_panel_open,
        },
      }));
    },
  };
});
