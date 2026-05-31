import { createContext, useContext, useState, type ReactNode } from 'react'
import type { Scenario } from '@/data/types'

interface Ctx {
  firmId: string
  setFirmId: (s: string) => void
  scenario: Scenario
  shockActive: boolean
  toggleShock: () => void
  reset: () => void
}

const ScenarioContext = createContext<Ctx | null>(null)

export function ScenarioProvider({ children }: { children: ReactNode }) {
  const [firmId, setFirmId] = useState('greenchem')
  const [scenario, setScenario] = useState<Scenario>('baseline')

  return (
    <ScenarioContext.Provider
      value={{
        firmId,
        setFirmId,
        scenario,
        shockActive: scenario === 'shock',
        toggleShock: () => setScenario((s) => (s === 'shock' ? 'baseline' : 'shock')),
        reset: () => setScenario('baseline'),
      }}
    >
      {children}
    </ScenarioContext.Provider>
  )
}

export function useScenario() {
  const v = useContext(ScenarioContext)
  if (!v) throw new Error('useScenario must be used within ScenarioProvider')
  return v
}
