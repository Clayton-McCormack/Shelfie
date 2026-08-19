import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';

import { addLibraryBook, analyseShelfPhoto, getLibrary } from './src/api';

const STATUS_LABELS = {
  auto: 'Added automatically',
  review: 'Needs review',
  unmatched: 'No catalog match',
};

function formatSeconds(milliseconds) {
  return (milliseconds / 1000).toFixed(2);
}

function ResultCard({ result, onConfirm, onCorrect, onDiscard, isSaving }) {
  const [isCorrecting, setIsCorrecting] = useState(false);
  const [title, setTitle] = useState(result.read_title);
  const [author, setAuthor] = useState(result.read_author);
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

      {(result.status === 'review' || result.status === 'unmatched') && !isCorrecting && (
        <View style={styles.reviewActions}>
          {result.status === 'review' && best && (
            <Pressable
              style={styles.confirmButton}
              disabled={isSaving}
              onPress={() => onConfirm(best)}
            >
              <Text style={styles.confirmButtonText}>Confirm</Text>
            </Pressable>
          )}
          <Pressable style={styles.textButton} disabled={isSaving} onPress={() => setIsCorrecting(true)}>
            <Text style={styles.textButtonLabel}>Correct</Text>
          </Pressable>
          <Pressable style={styles.textButton} disabled={isSaving} onPress={onDiscard}>
            <Text style={styles.textButtonLabel}>Discard</Text>
          </Pressable>
        </View>
      )}

      {isCorrecting && (
        <View style={styles.correction}>
          <Text style={styles.correctionTitle}>Correct this book</Text>
          <TextInput
            value={title}
            onChangeText={setTitle}
            placeholder="Title"
            style={styles.input}
          />
          <TextInput
            value={author}
            onChangeText={setAuthor}
            placeholder="Author"
            style={styles.input}
          />
          <View style={styles.reviewActions}>
            <Pressable
              style={styles.confirmButton}
              disabled={isSaving}
              onPress={() => onCorrect({ title, author })}
            >
              <Text style={styles.confirmButtonText}>Save correction</Text>
            </Pressable>
            <Pressable style={styles.textButton} disabled={isSaving} onPress={() => setIsCorrecting(false)}>
              <Text style={styles.textButtonLabel}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      )}
    </View>
  );
}

export default function App() {
  const [asset, setAsset] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [library, setLibrary] = useState([]);
  const [state, setState] = useState('idle');
  const [savingIndex, setSavingIndex] = useState(null);
  const [error, setError] = useState('');

  async function loadLibrary() {
    try {
      const data = await getLibrary();
      setLibrary(data.books);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadLibrary();
  }, []);

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
      loadLibrary();
    } catch (err) {
      setError(err.message);
      setState('ready');
    }
  }

  function removeResult(index) {
    setAnalysis((current) => ({
      ...current,
      results: current.results.filter((_, resultIndex) => resultIndex !== index),
    }));
  }

  async function saveReview(index, data) {
    setSavingIndex(index);
    setError('');
    try {
      const book = await addLibraryBook(data);
      setLibrary((current) => [book, ...current.filter((item) => item.id !== book.id)]);
      removeResult(index);
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingIndex(null);
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
            <Text style={styles.detection}>
              Local detection: {analysis.detection.count} candidate regions via{' '}
              {analysis.detection.route.replace('_', ' ')}.
            </Text>
            <Text style={styles.notice}>{analysis.detection.message}</Text>
            {analysis.detection.contact_sheets > 0 && (
              <Text style={styles.notice}>
                Prepared {analysis.detection.contact_sheets} numbered crop batch
                {analysis.detection.contact_sheets === 1 ? '' : 'es'} for title reading.
              </Text>
            )}
            <Text style={styles.notice}>{analysis.message}</Text>
            {analysis.timings_ms && (
              <Text style={styles.notice}>
                Timing: local {formatSeconds(analysis.timings_ms.local_detection)}s · Gemini{' '}
                {formatSeconds(analysis.timings_ms.hosted_reading)}s · matching{' '}
                {formatSeconds(analysis.timings_ms.matching)}s · total{' '}
                {formatSeconds(analysis.timings_ms.total)}s
              </Text>
            )}
            {analysis.results.map((result, index) => (
              <ResultCard
                key={`${result.read_title}-${index}`}
                result={result}
                isSaving={savingIndex === index}
                onConfirm={(candidate) => saveReview(index, { catalog_id: candidate.id, decision: 'confirmed' })}
                onCorrect={(correction) => saveReview(index, correction)}
                onDiscard={() => removeResult(index)}
              />
            ))}
          </View>
        )}

        <View style={styles.library}>
          <Text style={styles.sectionTitle}>My library</Text>
          {library.length === 0 && <Text style={styles.notice}>Confirmed books will appear here.</Text>}
          {library.map((book) => (
            <View key={book.id} style={styles.libraryRow}>
              <Text style={styles.libraryTitle}>{book.title}</Text>
              {!!book.author && <Text style={styles.libraryAuthor}>{book.author}</Text>}
            </View>
          ))}
        </View>
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
  library: { marginTop: 32 },
  sectionTitle: { fontSize: 21, fontWeight: '700', color: '#1c1a17' },
  notice: { color: '#6b645c', lineHeight: 20, marginTop: 8, marginBottom: 12 },
  detection: { color: '#1c1a17', fontWeight: '700', lineHeight: 20, marginTop: 8 },
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
  reviewActions: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 16 },
  confirmButton: { backgroundColor: '#1c1a17', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 7 },
  confirmButtonText: { color: '#fff', fontWeight: '600' },
  textButton: { paddingVertical: 10 },
  textButtonLabel: { color: '#5a4331', fontWeight: '600' },
  correction: { marginTop: 14 },
  correctionTitle: { fontWeight: '700', color: '#1c1a17', marginBottom: 8 },
  input: { borderWidth: 1, borderColor: '#d3cdc4', borderRadius: 7, padding: 10, marginTop: 8, color: '#1c1a17' },
  libraryRow: { borderBottomWidth: 1, borderBottomColor: '#e5e0d8', paddingVertical: 12 },
  libraryTitle: { color: '#1c1a17', fontWeight: '700' },
  libraryAuthor: { color: '#6b645c', marginTop: 3 },
});
