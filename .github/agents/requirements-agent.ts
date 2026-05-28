/**
 * Agent: requirements-agent
 * Opis: Generuje wymagania aplikacji na podstawie rozmów z użytkownikiem.
 * Format: opis ogólny + lista use case'ów.
 */

import { ChatCompletionRequestMessage, OpenAI } from "openai";

// Typy wymagań
interface Requirement {
  description: string;
  useCases: string[];
}

/**
 * Generuje wymagania na podstawie historii rozmowy.
 * @param conversation Array wiadomości (role: user/assistant, content: string)
 * @returns Requirement
 */
export async function generateRequirements(conversation: ChatCompletionRequestMessage[]): Promise<Requirement> {
  const systemPrompt = `Jesteś analitykiem biznesowym. Na podstawie rozmowy z użytkownikiem generujesz wymagania aplikacji w dwóch sekcjach:\n\n1. Opis ogólny (czym jest aplikacja, główne funkcje, dla kogo)\n2. Use case'y (krótkie, konkretne scenariusze użycia, wypunktowane)\n\nOdpowiadaj po polsku.`;

  const messages: ChatCompletionRequestMessage[] = [
    { role: "system", content: systemPrompt },
    ...conversation,
  ];

  // Użyj OpenAI (lub innego LLM) do wygenerowania wymagań
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });
  const completion = await openai.chat.completions.create({
    model: "gpt-4o", // lub inny model
    messages,
    max_tokens: 800,
    temperature: 0.2,
  });

  // Prosty parser: oczekujemy dwóch sekcji oddzielonych nagłówkami
  const content = completion.choices[0].message.content || "";
  const [desc, ...useCasesRaw] = content.split(/Use case[’'`]?y?:?/i);
  const description = desc.trim();
  const useCases = useCasesRaw.join("").split(/\n|•|\*/).map(s => s.trim()).filter(Boolean);

  return { description, useCases };
}

// Przykład użycia:
// const requirements = await generateRequirements(conversationHistory);
// console.log(requirements);