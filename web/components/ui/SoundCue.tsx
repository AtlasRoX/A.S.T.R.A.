'use client';

import { useEffect } from 'react';
import { alertSound } from '@/lib/sound';

/**
 * Sounds once when something a server page renders appears (say Ship Sense finding a shared cause). `id` names
 * that occurrence: the same id never sounds twice, in any tab or after a reload. Renders nothing.
 */
export function SoundCue({ id, sound }: { id: string; sound: Parameters<typeof alertSound>[1] }) {
  useEffect(() => alertSound(id, sound), [id, sound]);
  return null;
}
