// SPDX-License-Identifier: Apache-2.0
// Generates offline Material 3 tokens. No Node dependency is shipped to the browser.
import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
const require = createRequire(new URL('./theme-tools/package.json', import.meta.url));
const { build } = require('esbuild');
import { schemes } from './theme-tools/schemes.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const themes = [
  ['iris', 'Ирис', '#6750a4', 'Фирменный фиолетовый'],
  ['indigo', 'Индиго', '#3f51b5', 'Глубокий синий'],
  ['blue', 'Сапфир', '#1565c0', 'Ясный и собранный'],
  ['sky', 'Небо', '#0288d1', 'Прохладный голубой'],
  ['cyan', 'Лагуна', '#0097a7', 'Вода и свет'],
  ['teal', 'Бирюза', '#008577', 'Мягкая прохлада'],
  ['mint', 'Мята', '#39a980', 'Свежая зелень'],
  ['emerald', 'Изумруд', '#228b50', 'Насыщенный зелёный'],
  ['forest', 'Лес', '#397339', 'Тишина хвойного леса'],
  ['sage', 'Шалфей', '#74865c', 'Спокойный природный'],
  ['lime', 'Лайм', '#a4c639', 'Сочный жёлто-зелёный'],
  ['olive', 'Олива', '#808044', 'Тёплый землистый'],
  ['lemon', 'Лимон', '#d5b600', 'Солнечный жёлтый'],
  ['amber', 'Янтарь', '#d99800', 'Золотистое свечение'],
  ['honey', 'Мёд', '#ae7c30', 'Тёплый песочный'],
  ['peach', 'Персик', '#e69b78', 'Мягкий абрикосовый'],
  ['orange', 'Мандарин', '#e77817', 'Энергичный оранжевый'],
  ['terracotta', 'Терракота', '#a6573c', 'Обожжённая глина'],
  ['coral', 'Коралл', '#e26365', 'Тёплый розово-красный'],
  ['rose', 'Роза', '#bf5079', 'Пыльный розовый'],
  ['magenta', 'Фуксия', '#b03a95', 'Выразительный пурпурный'],
  ['plum', 'Слива', '#84469b', 'Вечерний фиолетовый'],
  ['lavender', 'Лаванда', '#8b80c4', 'Нежный сиреневый'],
  ['slate', 'Сланец', '#607d8b', 'Сдержанный серо-синий'],
  ['graphite', 'Графит', '#6e6e73', 'Почти монохромный'],
  ['midnight', 'Полночь', '#273860', 'Глубокий ночной синий'],
  ['denim', 'Деним', '#42638a', 'Спокойный джинсовый'],
  ['cobalt', 'Кобальт', '#2046a2', 'Насыщенный кобальтовый'],
  ['glacier', 'Ледник', '#74a8ba', 'Светлый ледяной голубой'],
  ['fjord', 'Фьорд', '#426f85', 'Серо-синий морской'],
  ['ocean', 'Океан', '#00677a', 'Глубокий сине-зелёный'],
  ['petrol', 'Петроль', '#245e61', 'Тёмная морская волна'],
  ['jade', 'Нефрит', '#3e816c', 'Мягкий нефритовый'],
  ['eucalyptus', 'Эвкалипт', '#668d7c', 'Приглушённая зелень'],
  ['pine', 'Сосна', '#315f48', 'Глубокий хвойный'],
  ['moss', 'Мох', '#657348', 'Зелёный с землистым оттенком'],
  ['pistachio', 'Фисташка', '#a6ad71', 'Мягкий фисташковый'],
  ['basil', 'Базилик', '#668335', 'Свежий травяной'],
  ['mustard', 'Горчица', '#a78229', 'Тёплый горчичный'],
  ['bronze', 'Бронза', '#8d673c', 'Приглушённый бронзовый'],
  ['copper', 'Медь', '#aa5a38', 'Тёплый медный'],
  ['clay', 'Глина', '#b67860', 'Натуральный глиняный'],
  ['sand', 'Песок', '#bba37e', 'Светлый песочный'],
  ['cocoa', 'Какао', '#795b54', 'Тёплый коричневый'],
  ['cherry', 'Вишня', '#a63f52', 'Глубокий ягодный'],
  ['cranberry', 'Клюква', '#a6406c', 'Холодный ягодный'],
  ['wine', 'Вино', '#803e59', 'Тёмный винный'],
  ['orchid', 'Орхидея', '#a15aa5', 'Насыщенный цветочный'],
  ['lilac', 'Сирень', '#a987b9', 'Мягкий сиреневый'],
  ['amethyst', 'Аметист', '#7450a5', 'Глубокий аметистовый'],
  ['dusk', 'Сумерки', '#666385', 'Приглушённый фиолетовый'],
  ['steel', 'Сталь', '#697b91', 'Прохладный серо-синий'],
  ['stone', 'Камень', '#85837b', 'Нейтральный каменный'],
  ['ash', 'Пепел', '#757d79', 'Спокойный серо-зелёный'],
  ['rosewood', 'Палисандр', '#8d6065', 'Приглушённый розово-коричневый'],
  ['ruby', 'Рубин', '#af1544', 'Рубин'],
  ['garnet', 'Гранат', '#733043', 'Гранат'],
  ['poppy', 'Мак', '#f04535', 'Мак'],
  ['brick', 'Кирпич', '#994938', 'Кирпич'],
  ['cinnabar', 'Киноварь', '#c84b31', 'Киноварь'],
  ['paprika', 'Паприка', '#c85224', 'Паприка'],
  ['sienna', 'Сиена', '#a0522d', 'Сиена'],
  ['cinnamon', 'Корица', '#945429', 'Корица'],
  ['apricot', 'Абрикос', '#ed9859', 'Абрикос'],
  ['pumpkin', 'Тыква', '#d97723', 'Тыква'],
  ['marigold', 'Бархатцы', '#fdac2d', 'Бархатцы'],
  ['ochre', 'Охра', '#b48328', 'Охра'],
  ['saffron', 'Шафран', '#fac62f', 'Шафран'],
  ['wheat', 'Пшеница', '#dab66d', 'Пшеница'],
  ['straw', 'Солома', '#d3c079', 'Солома'],
  ['vanilla', 'Ваниль', '#d6ca8e', 'Ваниль'],
  ['pear', 'Груша', '#bac740', 'Груша'],
  ['matcha', 'Матча', '#97b762', 'Матча'],
  ['fern', 'Папоротник', '#568d48', 'Папоротник'],
  ['clover', 'Клевер', '#278541', 'Клевер'],
  ['meadow', 'Луг', '#69b551', 'Луг'],
  ['bamboo', 'Бамбук', '#859f49', 'Бамбук'],
  ['spruce', 'Ель', '#2c614c', 'Ель'],
  ['malachite', 'Малахит', '#239a6a', 'Малахит'],
  ['absinthe', 'Абсент', '#76b891', 'Абсент'],
  ['seafoam', 'Пена', '#7acfb3', 'Пена'],
  ['amazonite', 'Амазонит', '#31ab94', 'Амазонит'],
  ['verdigris', 'Патина', '#4e9285', 'Патина'],
  ['juniper', 'Можжевельник', '#42796c', 'Можжевельник'],
  ['atoll', 'Атолл', '#24b4af', 'Атолл'],
  ['surf', 'Прибой', '#378f9b', 'Прибой'],
  ['ice', 'Лёд', '#8bccdc', 'Лёд'],
  ['rain', 'Дождь', '#6995ad', 'Дождь'],
  ['horizon', 'Горизонт', '#629fcb', 'Горизонт'],
  ['azurite', 'Азурит', '#246ca8', 'Азурит'],
  ['cornflower', 'Василёк', '#6387d1', 'Василёк'],
  ['ultramarine', 'Ультрамарин', '#364ba8', 'Ультрамарин'],
  ['storm', 'Шторм', '#525f83', 'Шторм'],
  ['ink', 'Чернила', '#414568', 'Чернила'],
  ['cosmos', 'Космос', '#47336d', 'Космос'],
  ['violet', 'Фиалка', '#7749b6', 'Фиалка'],
  ['wisteria', 'Глициния', '#9681c9', 'Глициния'],
  ['heather', 'Вереск', '#986fa5', 'Вереск'],
  ['mallow', 'Мальва', '#b274af', 'Мальва'],
  ['bougainvillea', 'Бугенвиллея', '#bc3f8e', 'Бугенвиллея'],
  ['cyclamen', 'Цикламен', '#c64d88', 'Цикламен'],
  ['peony', 'Пион', '#d37798', 'Пион'],
  ['blush', 'Румянец', '#db9d9c', 'Румянец'],
  ['salmon', 'Лосось', '#ea8075', 'Лосось'],
  ['quartz', 'Кварц', '#ae899d', 'Кварц'],
  ['mulberry', 'Шелковица', '#773957', 'Шелковица'],
  ['raisin', 'Изюм', '#624558', 'Изюм'],
  ['espresso', 'Эспрессо', '#5d4438', 'Эспрессо'],
  ['chestnut', 'Каштан', '#8b4e3e', 'Каштан'],
  ['truffle', 'Трюфель', '#746354', 'Трюфель'],
  ['linen', 'Лён', '#b7a085', 'Лён'],
  ['flint', 'Кремень', '#78716f', 'Кремень'],
  ['granite', 'Гранит', '#746e79', 'Гранит'],
  ['silver', 'Серебро', '#909ba5', 'Серебро'],
  ['pewter', 'Олово', '#899692', 'Олово'],
  ['lichen', 'Лишайник', '#98a380', 'Лишайник'],
  ['agate', 'Агат', '#896960', 'Агат'],
  ['opal', 'Опал', '#98b9b2', 'Опал'],
  ['moonstone', 'Адуляр', '#8d9ba9', 'Адуляр'],
  ['aurora', 'Аврора', '#4dbaab', 'Аврора'],
];
const catalog = themes.map(([id, name, seed, description]) => ({
  id, name, seed, description, schemes: schemes(seed, id === 'graphite')
}));
let css = '/* Generated by scripts/generate-themes.mjs; Apache-2.0. Do not edit by hand. */\n';
for (const theme of catalog) {
  for (const mode of ['light', 'dark']) {
    // Swatch labels inherit the chosen mode but preview their own palette.
    const defaults = theme.id === 'iris' && mode === 'light' ? ':root,\n' : '';
    css += `${defaults}:root[data-theme="${theme.id}"][data-mode="${mode}"],\n:root[data-mode="${mode}"] [data-palette="${theme.id}"] {\n`;
    css += `  color-scheme: ${mode};\n`;
    for (const [role, hex] of Object.entries(theme.schemes[mode])) css += `  --md-${role}: ${hex};\n`;
    css += '}\n';
  }
}
await writeFile(resolve(root, 'ui/themes.css'), css);
await writeFile(resolve(root, 'ui/themes.js'), '// Generated by scripts/generate-themes.mjs; Apache-2.0.\nwindow.AnyGameVoiceThemes = ' + JSON.stringify(catalog, null, 2) + ';\n');
console.log(`Generated ${catalog.length} palettes, ${catalog.length * 2} schemes.`);
await build({
  entryPoints: [resolve(root, 'scripts/theme-tools/schemes.mjs')],
  outfile: resolve(root, 'ui/custom-color.js'), bundle: true, minify: true,
  format: 'iife', globalName: 'StudioColor', legalComments: 'inline'
});
