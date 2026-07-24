import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

// Redimensiona a foto antes de enviar (mesmo espirito da compressao do
// lado web): reduz o tamanho do upload sem depender de wifi rapido no
// deposito.
export async function compressImage(uri: string, maxWidth = 1600, quality = 0.7): Promise<string> {
  const context = ImageManipulator.manipulate(uri);
  context.resize({ width: maxWidth });
  const rendered = await context.renderAsync();
  const resultado = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: quality });
  return resultado.uri;
}
