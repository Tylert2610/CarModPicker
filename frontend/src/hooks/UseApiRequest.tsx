import { type AxiosResponse } from 'axios';
import { useCallback, useState } from 'react';
import { getApiErrorMessage } from '../utils/apiError';

interface UseApiRequestReturn<TData, TPayload> {
  data: TData | null;
  error: string | null;
  isLoading: boolean;
  executeRequest: (payload?: TPayload) => Promise<TData | null>;
  setError: (message: string | null) => void;
}

const parseApiError = (err: unknown): string =>
  getApiErrorMessage(err, 'An unexpected error occurred.');

function useApiRequest<TData, TPayload = unknown>(
  requestFn: (payload: TPayload) => Promise<AxiosResponse<TData>>
): UseApiRequestReturn<TData, TPayload> {
  const [data, setData] = useState<TData | null>(null);
  const [error, setErrorState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const executeRequest = useCallback(
    async (payload?: TPayload): Promise<TData | null> => {
      setIsLoading(true);
      setErrorState(null);
      try {
        // Use empty object as default payload if none provided
        const actualPayload = (payload ?? {}) as TPayload;
        const response = await requestFn(actualPayload);
        setData(response.data);
        setIsLoading(false);
        return response.data;
      } catch (err) {
        const parsedError = parseApiError(err);
        setErrorState(parsedError);
        setIsLoading(false);
        return null;
      }
    },
    [requestFn]
  );

  const setError = useCallback((message: string | null) => {
    setErrorState(message);
  }, []);

  return { data, error, isLoading, executeRequest, setError };
}

export default useApiRequest;
