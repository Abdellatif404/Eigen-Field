import type { IconifyJSON } from '@iconify/react';

import { addCollection } from '@iconify/react';
import mdiIconsAll from '@iconify-json/mdi/icons.json';
import solarIconsAll from '@iconify-json/solar/icons.json';
import vscodeIconsAll from '@iconify-json/vscode-icons/icons.json';

import allIcons from './icon-sets';

// ----------------------------------------------------------------------

const USED_ICONS = {
  solar: [
    'check-circle-bold',
    'home-angle-bold-duotone',
    'pen-bold',
    'settings-bold-duotone',
    'share-bold',
    'shield-keyhole-bold-duotone',
    'trash-bin-trash-bold',
  ],
  'vscode-icons': [
    'file-type-pdf2',
  ]
};

// ----------------------------------------------------------------------

function extractUsedIcons(
  fullLibrary: IconifyJSON,
  usedNames: string[]
): IconifyJSON {
  const extracted: IconifyJSON = {
    prefix: fullLibrary.prefix,
    icons: {},
  };

  if (fullLibrary.width) extracted.width = fullLibrary.width;
  if (fullLibrary.height) extracted.height = fullLibrary.height;

  usedNames.forEach((iconName) => {
    if (fullLibrary.icons[iconName]) {
      extracted.icons[iconName] = fullLibrary.icons[iconName];
    }
  });

  return extracted;
}

const solarIcons = extractUsedIcons(
  solarIconsAll as IconifyJSON,
  USED_ICONS.solar
);
const vscodeIcons = extractUsedIcons(
  vscodeIconsAll as IconifyJSON,
  USED_ICONS['vscode-icons']
);

// ----------------------------------------------------------------------

export const iconSets = Object.entries(allIcons).reduce((acc, [key, value]) => {
  const [prefix, iconName] = key.split(':');
  const existingPrefix = acc.find((item) => item.prefix === prefix);

  if (existingPrefix) {
    existingPrefix.icons[iconName] = value;
  } else {
    acc.push({
      prefix,
      icons: { [iconName]: value },
    });
  }

  return acc;
}, [] as IconifyJSON[]);

export const allIconNames = [
  ...Object.keys(allIcons),
  ...USED_ICONS.solar.map((name) => `solar:${name}`),
  ...USED_ICONS['vscode-icons'].map((name) => `vscode-icons:${name}`),
];

export type IconifyName = keyof typeof allIcons | string;

// ----------------------------------------------------------------------

let areIconsRegistered = false;

export function registerIcons() {
  if (areIconsRegistered) {
    return;
  }

  iconSets.forEach((iconSet) => {
    const iconSetConfig = {
      ...iconSet,
      width: (iconSet.prefix === 'carbon' && 32) || 24,
      height: (iconSet.prefix === 'carbon' && 32) || 24,
    };
    addCollection(iconSetConfig);
  });

  addCollection(solarIcons);
  addCollection(vscodeIcons);

  areIconsRegistered = true;
}
