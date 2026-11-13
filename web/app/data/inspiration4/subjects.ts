/**
 * The four Inspiration4 crew members, in the order the dataset lists them.
 *
 * The dataset identifies them as C001-C004. These are the names NASA published with the
 * study; they are not characters from the dataset.
 */
export const SUBJECT_LABEL: Record<string, string> = {
  C001: 'Crew 1',
  C002: 'Crew 2',
  C003: 'Crew 3',
  C004: 'Crew 4',
};

/**
 * One colour per crew member, so the same person is the same colour on every chart. The palette (i4.module.css)
 * leaves out the status colours, which mark Watch and Act.
 */
export const SUBJECT_COLOR: Record<string, string> = {
  C001: 'var(--crew-1)',
  C002: 'var(--crew-2)',
  C003: 'var(--crew-3)',
  C004: 'var(--crew-4)',
};

/** The seven sampling points, in days relative to launch. */
export const TIMEPOINT_LABEL: Record<string, string> = {
  'L-92': '92 d before',
  'L-44': '44 d before',
  'L-3': '3 d before',
  'R+1': '1 d after',
  'R+45': '45 d after',
  'R+82': '82 d after',
  'R+194': '194 d after',
};
