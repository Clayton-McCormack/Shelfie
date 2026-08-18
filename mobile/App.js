import { useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';

import { analyseShelfPhoto } from './src/api';

const STATUS_LABELS = {
  auto: 'Added automatically',
  review: 'Needs review',
  unmatched: 'No catalog match',
};

function ResultCard({ result }) {
  const best = result.candidates[0];

  return (
    <View style={styles.resultCard}>
      <View style={styles.resultHeader}>
        <Text style={styles.readTitle}>{result.read_title || 'Unreadable spine'}</Text>
        <Text style={[styles.status, styles[`status_${result.status}`]]}>
          {STATUS_LABELS[result.status]}
        </Text>
      </View>

      {!!result.read_author && <Text style={styles.readAuthor}>{result.read_author}</Text>}

      {best && (
        <Text style={styles.match}>
          Suggested: {best.title} — {best.author}
        </Text>
      )}

      <Text style={styles.confidence}>Confidence: {Math.round(result.confidence * 100)}%</Text>

      {result.reasons.map((reason) => (
        <Text key={reason} style={styles.reason}>
          {reason}
        </Text>
      ))}
    </View>
  );
}

export default function App() {
  const [asset, setAsset] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [state, setState] = useState('idle');
  const [error, setError] = useState('');

  async function useImagePicker(openPicker) {
    setError('');
    const response = await openPicker();
    if (response.canceled) return;

    setAsset(response.assets[0]);
    setAnalysis(null);
    setState('ready');
  }

  function choosePhoto() {
    return useImagePicker(() =>
      ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 }),
    );
  }

  async function takePhoto() {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      setError('Camera permission is required to take a bookshelf photo.');
      return;
    }

    return useImagePicker(() =>
      ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.8 }),
    );
  }

  async function analyse() {
    if (!asset) return;

    setState('analysing');
    setError('');
    try {
      const data = await analyseShelfPhoto(asset);
      setAnalysis(data);
      setState('complete');
    } catch (err) {
      setError(err.message);
      setState('ready');
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Shelfie</Text>
        <Text style={styles.subtitle}>Turn a bookshelf photo into a library.</Text>

        <View style={styles.actions}>
          <Pressable style={styles.primaryButton} onPress={takePhoto} disabled={state === 'analysing'}>
            <Text style={styles.primaryButtonText}>Take bookshelf photo</Text>
          </Pressable>
          <Pressable style={styles.secondaryButton} onPress={choosePhoto} disabled={state === 'analysing'}>
            <Text style={styles.secondaryButtonText}>Choose a photo</Text>
          </Pressable>
        </View>

        {asset && <Image source={{ uri: asset.uri }} style={styles.preview} />}

        {state === 'ready' && (
          <Pressable style={styles.primaryButton} onPress={analyse}>
            <Text style={styles.primaryButtonText}>Analyse this shelf</Text>
          </Pressable>
        )}

        {state === 'analysing' && (
          <View style={styles.loading}>
            <ActivityIndicator />
            <Text style={styles.loadingText}>Uploading and matching books…</Text>
          </View>
        )}

        {!!error && <Text style={styles.error}>{error}</Text>}

        {analysis && (
          <View style={styles.results}>
            <Text style={styles.sectionTitle}>Analysis results</Text>
            <Text style={styles.notice}>{analysis.message}</Text>
            {analysis.results.map((result, index) => (
              <ResultCard key={`${result.read_title}-${index}`} result={result} />
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#faf9f7' },
  content: { padding: 24, paddingBottom: 48 },
  title: { fontSize: 34, fontWeight: '700', color: '#1c1a17' },
  subtitle: { fontSize: 16, color: '#6b645c', marginTop: 4, marginBottom: 24 },
  actions: { gap: 10, marginBottom: 20 },
  primaryButton: { backgroundColor: '#1c1a17', paddingVertical: 14, borderRadius: 8, alignItems: 'center' },
  primaryButtonText: { color: '#fff', fontWeight: '600' },
  secondaryButton: { borderWidth: 1, borderColor: '#1c1a17', paddingVertical: 13, borderRadius: 8, alignItems: 'center' },
  secondaryButtonText: { color: '#1c1a17', fontWeight: '600' },
  preview: { width: '100%', aspectRatio: 4 / 3, borderRadius: 10, marginBottom: 20, backgroundColor: '#e5e0d8' },
  loading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginTop: 20 },
  loadingText: { marginLeft: 10, color: '#6b645c' },
  error: { color: '#a32b2b', marginTop: 16, lineHeight: 20 },
  results: { marginTop: 28 },
  sectionTitle: { fontSize: 21, fontWeight: '700', color: '#1c1a17' },
  notice: { color: '#6b645c', lineHeight: 20, marginTop: 8, marginBottom: 12 },
  resultCard: { backgroundColor: '#fff', borderRadius: 10, borderWidth: 1, borderColor: '#e5e0d8', padding: 16, marginTop: 10 },
  resultHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  readTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: '#1c1a17' },
  readAuthor: { marginTop: 3, color: '#6b645c' },
  status: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  status_auto: { color: '#1f7a4d' },
  status_review: { color: '#9a6500' },
  status_unmatched: { color: '#a32b2b' },
  match: { marginTop: 12, color: '#1c1a17', lineHeight: 20 },
  confidence: { marginTop: 8, color: '#6b645c' },
  reason: { marginTop: 7, color: '#6b645c', fontSize: 13, lineHeight: 18 },
});
