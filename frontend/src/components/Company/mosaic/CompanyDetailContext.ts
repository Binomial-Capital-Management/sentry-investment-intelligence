import { createContext, useContext } from 'react';

export interface CompanyDetailContextValue {
  ticker: string;
}

export const CompanyDetailContext = createContext<CompanyDetailContextValue>({
  ticker: '',
});

export function useCompanyDetail(): CompanyDetailContextValue {
  return useContext(CompanyDetailContext);
}
