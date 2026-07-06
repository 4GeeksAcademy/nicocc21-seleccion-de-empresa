export const filtrar = <T>(items: T[], criterio: (item: T) => boolean): T[] => {
  return items.filter(criterio);
};

export const ordenar = <T>(items: T[], comparador: (a: T, b: T) => number): T[] => {
  return [...items].sort(comparador);
};

export const buscar = <T>(items: T[], criterio: (item: T) => boolean): T | undefined => {
  return items.find(criterio);
};

export const agruparPor = <T, K extends string | number>(
  items: T[],
  obtenerClave: (item: T) => K
): Record<K, T[]> => {
  return items.reduce((acc, item) => {
    const key = obtenerClave(item);
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {} as Record<K, T[]>);
};
