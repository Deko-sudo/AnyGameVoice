// SPDX-License-Identifier: Apache-2.0
import { Hct, SchemeTonalSpot, SchemeNeutral, MaterialDynamicColors, argbFromHex, hexFromArgb }
  from '@material/material-color-utilities';
const roles = ['primary', 'onPrimary', 'primaryContainer', 'onPrimaryContainer',
  'secondary', 'onSecondary', 'secondaryContainer', 'onSecondaryContainer',
  'tertiary', 'onTertiary', 'tertiaryContainer', 'onTertiaryContainer',
  'surface', 'surfaceDim', 'surfaceBright', 'surfaceContainerLowest', 'surfaceContainerLow',
  'surfaceContainer', 'surfaceContainerHigh', 'surfaceContainerHighest', 'onSurface',
  'onSurfaceVariant', 'outline', 'outlineVariant', 'error', 'onError', 'errorContainer',
  'onErrorContainer', 'inverseSurface', 'inverseOnSurface', 'inversePrimary'];
const kebab = value => value.replace(/[A-Z]/g, match => '-' + match.toLowerCase());
export function schemes(seed, neutral = false) {
  const Scheme = neutral ? SchemeNeutral : SchemeTonalSpot;
  return Object.fromEntries(['light', 'dark'].map(mode => {
    const scheme = new Scheme(Hct.fromInt(argbFromHex(seed)), mode === 'dark', 0);
    return [mode, Object.fromEntries(roles.map(role => [kebab(role), hexFromArgb(MaterialDynamicColors[role].getArgb(scheme))]))];
  }));
}
