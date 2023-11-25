export const getBotUpdates = () =>
  fetch(
    "https://api.telegram.org/bot{token}/getUpdates"
  ).then((response) => response.json());

  export const getUserTelegramId = async (uniqueString: any) => {
    const { result } = await getBotUpdates();
  
    const messageUpdates = result.filter(
      (update: { message?: { text?: string } }) => update.message?.text !== undefined
    );
  
    const userUpdate = messageUpdates.find(
      (update: { message?: { text?: string } }) => update.message?.text === `/start ${uniqueString}`
    );
  
    return userUpdate?.message?.from?.id;
  };
  