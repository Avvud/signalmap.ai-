import React from 'react';
import { Globe, Database, Filter, Cpu, CheckCircle2, AlertCircle } from 'lucide-react';

const STEPS = [
  { key: 'queued', label: 'Queued', icon: Globe },
  { key: 'fetching_sources', label: 'Fetching Data Sources', icon: Database },
  { key: 'normalizing', label: 'Normalizing Evidence', icon: Filter },
  { key: 'synthesizing', label: 'Groq Dual Synthesis', icon: Cpu },
  { key: 'completed', label: 'Report Generated', icon: CheckCircle2 }
];

const STATUS_INDEX = {
  'queued': 0,
  'fetching_sources': 1,
  'normalizing': 2,
  'analyzing': 3,
  'synthesizing': 3,
  'completed': 4,
  'failed': -1
};

export default function PipelineStepper({ currentStatus }) {
  const currentIndex = STATUS_INDEX[currentStatus] ?? 0;

  return (
    <div className="stepper-container">
      {STEPS.map((step, idx) => {
        let state = 'pending';

        if (currentStatus === 'failed') {
          state = 'failed';
        } else if (idx < currentIndex) {
          state = 'completed';
        } else if (idx === currentIndex) {
          state = 'active';
        }

        const Icon = currentStatus === 'failed' && idx === currentIndex ? AlertCircle : step.icon;

        return (
          <div key={step.key} className={`stepper-step ${state}`}>
            <div className="step-circle">
              <Icon size={18} />
            </div>
            <span className="step-label">{step.label}</span>
          </div>
        );
      })}
    </div>
  );
}
