import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, ActivityIndicator, Alert, TouchableOpacity } from 'react-native';
import { ApiService } from '../services/api';
import { ScreenContainer } from '../components/ScreenContainer';
import { GlassCard } from '../components/GlassCard';
import { GlowingButton } from '../components/GlowingButton';
import { COLORS } from '../theme/colors';

export const PetsScreen = () => {
  const [pets, setPets] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [feedingPetName, setFeedingPetName] = useState<string | null>(null);

  const fetchPets = async () => {
    setLoading(true);
    try {
      const data = await ApiService.getPets();
      setPets(data.pets || []);
    } catch (err: any) {
      console.error(err);
      Alert.alert('Load Error', 'Failed to retrieve household pet profiles.');
    } finally {
      setLoading(false);
    }
  };

  const handleFeedPet = async (name: string) => {
    setFeedingPetName(name);
    try {
      const res = await ApiService.feedPet(name);
      if (res.success) {
        Alert.alert('Feeding Logged', res.message);
        fetchPets(); // Re-fetch updated last_fed timestamp
      }
    } catch (err: any) {
      console.error(err);
      Alert.alert('Feed Error', err.message || `Failed to log feeding for ${name}.`);
    } finally {
      setFeedingPetName(null);
    }
  };

  useEffect(() => {
    fetchPets();
  }, []);

  const renderPetItem = ({ item }: { item: any }) => {
    const isFeedingThisPet = feedingPetName === item.name;
    const formattedLastFed = item.last_fed 
      ? new Date(item.last_fed).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : 'Never / Stale';

    return (
      <GlassCard title={item.name} borderColor={COLORS.secondary}>
        <View style={styles.petGrid}>
          <View style={styles.infoCol}>
            <View style={styles.row}>
              <Text style={styles.label}>SPECIES</Text>
              <Text style={styles.value}>{item.species.toUpperCase()}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>BREED</Text>
              <Text style={styles.value}>{item.breed || 'Unknown'}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>AGE</Text>
              <Text style={styles.value}>{item.age ? `${item.age} yrs` : 'N/A'}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>LAST FED</Text>
              <Text style={[styles.value, item.last_fed ? { color: COLORS.primary } : { color: COLORS.textMuted }]}>
                {formattedLastFed}
              </Text>
            </View>
          </View>

          <View style={styles.actionCol}>
            <GlowingButton
              onPress={() => handleFeedPet(item.name)}
              title="Feed"
              variant="secondary"
              loading={isFeedingThisPet}
              style={styles.feedBtn}
            />
          </View>
        </View>
      </GlassCard>
    );
  };

  return (
    <ScreenContainer>
      {loading && pets.length === 0 ? (
        <ActivityIndicator color={COLORS.primary} style={styles.loader} />
      ) : (
        <FlatList
          data={pets}
          keyExtractor={(item) => item.name}
          renderItem={renderPetItem}
          onRefresh={fetchPets}
          refreshing={loading}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No pets registered in memory cache.</Text>
          }
          showsVerticalScrollIndicator={false}
        />
      )}
    </ScreenContainer>
  );
};

const styles = StyleSheet.create({
  loader: {
    marginTop: 40,
  },
  petGrid: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  infoCol: {
    flex: 1.4,
  },
  actionCol: {
    flex: 0.6,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  row: {
    flexDirection: 'row',
    marginVertical: 3,
    alignItems: 'center',
  },
  label: {
    color: COLORS.textMuted,
    fontSize: 9,
    fontWeight: 'bold',
    width: 75,
    letterSpacing: 1,
  },
  value: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '600',
  },
  feedBtn: {
    width: '100%',
    height: 40,
  },
  emptyText: {
    color: COLORS.textMuted,
    textAlign: 'center',
    paddingVertical: 30,
    fontSize: 13,
  },
});
