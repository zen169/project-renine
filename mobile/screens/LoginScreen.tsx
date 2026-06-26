import React, { useState } from 'react';
import { StyleSheet, Text, View, Alert } from 'react-native';
import { useAuth } from '../services/auth';
import { ScreenContainer } from '../components/ScreenContainer';
import { GlassCard } from '../components/GlassCard';
import { GlowingInput } from '../components/GlowingInput';
import { GlowingButton } from '../components/GlowingButton';
import { COLORS } from '../theme/colors';

export const LoginScreen = () => {
  const { login, serverUrl } = useAuth();
  const [url, setUrl] = useState<string>(serverUrl || 'https://127.0.0.1:8000');
  const [username, setUsername] = useState<string>('admin');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const handleLogin = async () => {
    if (!url.trim()) {
      Alert.alert('Error', 'API Server URL is required');
      return;
    }
    if (!password.trim()) {
      Alert.alert('Error', 'Password is required');
      return;
    }

    setLoading(true);
    try {
      const success = await login(password, url, username);
      if (!success) {
        Alert.alert('Error', 'Invalid credentials');
      }
    } catch (err: any) {
      console.error(err);
      Alert.alert('Connection Failed', err.message || 'Could not reach server. Verify the URL and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScreenContainer scrollable>
      <View style={styles.logoContainer}>
        <Text style={styles.logoGlow}>RENINE</Text>
        <Text style={styles.logoSubtitle}>MOBILE COMPANION</Text>
      </View>

      <GlassCard title="Establish Link" style={styles.card}>
        <Text style={styles.instruction}>
          Provide connection credentials to authorize remote link with the main core server.
        </Text>

        <GlowingInput
          label="API Core Server URL"
          value={url}
          onChangeText={setUrl}
          placeholder="https://127.0.0.1:8000"
          autoCapitalize="none"
          autoCorrect={false}
        />

        <GlowingInput
          label="Ident Operator Code"
          value={username}
          onChangeText={setUsername}
          placeholder="admin"
          autoCapitalize="none"
          autoCorrect={false}
        />

        <GlowingInput
          label="Decryption Passphrase"
          value={password}
          onChangeText={setPassword}
          placeholder="••••••••"
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />

        <GlowingButton
          onPress={handleLogin}
          title="Authenticate"
          loading={loading}
          style={styles.button}
        />
      </GlassCard>
    </ScreenContainer>
  );
};

const styles = StyleSheet.create({
  logoContainer: {
    alignItems: 'center',
    marginTop: 60,
    marginBottom: 40,
  },
  logoGlow: {
    fontSize: 48,
    fontWeight: '900',
    color: COLORS.primary,
    letterSpacing: 8,
    textShadowColor: COLORS.primary,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 15,
  },
  logoSubtitle: {
    color: COLORS.secondary,
    fontSize: 11,
    letterSpacing: 4,
    fontWeight: 'bold',
    marginTop: 8,
  },
  card: {
    marginTop: 10,
  },
  instruction: {
    color: COLORS.textSecondary,
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 20,
  },
  button: {
    marginTop: 20,
  },
});
