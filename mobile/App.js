import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

import { API_BASE_URL } from './src/config';
import { request } from './src/api';

export default function App() {
  // 'checking' | 'ok' | 'error' — there is a rendered state for each, so the
  // screen is never blank while work is in flight or after a failure.
  const [status, setStatus] = useState('checking');
  const [message, setMessage] = useState('');

  const checkHealth = useCallback(async () => {
    setStatus('checking');
    setMessage('');
    try {
      const data = await request('/api/health/');
      setStatus('ok');
      setMessage(`Backend replied: ${data.status}`);
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="auto" />
      <View style={styles.content}>
        <Text style={styles.title}>Shelfie</Text>
        <Text style={styles.subtitle}>Bookshelf to library inventory</Text>

        <View style={styles.card}>
          <Text style={styles.cardHeading}>Backend connection</Text>
          <Text style={styles.mono}>{API_BASE_URL ?? 'address not detected'}</Text>

          {status === 'checking' && (
            <View style={styles.row}>
              <ActivityIndicator />
              <Text style={styles.checking}>Checking…</Text>
            </View>
          )}

          {status === 'ok' && <Text style={styles.ok}>{message}</Text>}

          {status === 'error' && (
            <>
              <Text style={styles.error}>{message}</Text>
              <Pressable style={styles.button} onPress={checkHealth}>
                <Text style={styles.buttonText}>Try again</Text>
              </Pressable>
            </>
          )}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#faf9f7' },
  content: { flex: 1, padding: 24, justifyContent: 'center' },
  title: { fontSize: 34, fontWeight: '700', color: '#1c1a17' },
  subtitle: { fontSize: 16, color: '#6b645c', marginTop: 4, marginBottom: 32 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: '#e5e0d8',
  },
  cardHeading: { fontSize: 13, fontWeight: '600', color: '#6b645c', textTransform: 'uppercase' },
  mono: { fontFamily: 'monospace', fontSize: 13, color: '#1c1a17', marginTop: 8 },
  row: { flexDirection: 'row', alignItems: 'center', marginTop: 16 },
  checking: { marginLeft: 10, color: '#6b645c' },
  ok: { marginTop: 16, color: '#1f7a4d', fontWeight: '600' },
  error: { marginTop: 16, color: '#a32b2b', lineHeight: 20 },
  button: {
    marginTop: 16,
    backgroundColor: '#1c1a17',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonText: { color: '#fff', fontWeight: '600' },
});
