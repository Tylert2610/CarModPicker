import { useState, useCallback } from 'react';
import { AxiosError, type AxiosResponse } from 'axios';
import type { HTTPValidationError, ValidationError } from '../types/Api';

interface UseApiRequestReturn<TData, TPayload> {
  data: TData | null;
  error: string | null;
  isLoading: boolean;
  executeRequest: (payload?: TPayload) => Promise<TData | null>;
  setError: (message: string | null) => void;
}

const parseApiError = (err: unknown): string => {
  const axiosError = err as AxiosError<HTTPValidationError>;
  if (axiosError.isAxiosError && axiosError.response?.data) {
    const responseData = axiosError.response.data;
    if (responseData.detail) {
      if (Array.isArray(responseData.detail)) {
        return responseData.detail
          .map((detailItem: ValidationError) => detailItem.msg)
          .join('. ');
      } else if (typeof responseData.detail === 'string') {
        return responseData.detail;
      }
    }
    // Check for alternative message formats
    if ('message' in responseData && typeof responseData.message === 'string') {
      return responseData.message;
    }
    return 'An unexpected error format was received from the server.';
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return 'An unexpected error occurred.';
};

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
      setData(null);
      try {
        // Use empty object as default payload if none provided
        const actualPayload = (payload ?? {}) as TPayload;
        const response = await requestFn(actualPayload);
        setData(response.data);
        setIsLoading(false);
        return response.data;
      } catch (err) {
        const parsedError = parseApiError(err);
        console.error('API Request Failed:', err);
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
