export const getBotUpdates = () =>
  fetch(
    "https://api.telegram.org/bot{token}/getUpdates"
  ).then((response) => response.json());

export const getUserTelegramId = async (uniqueString) => {
  const { result } = await getBotUpdates();

  const messageUpdates = result.filter(
    ({ message }) => message?.text !== undefined
  );

  const userUpdate = messageUpdates.find(
    ({ message }) => message.text === `/start ${uniqueString}`
  );

  return userUpdate.message.from.id;
};