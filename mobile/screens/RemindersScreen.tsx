import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, ActivityIndicator, Alert } from 'react-native';
import { ApiService } from '../services/api';
import { ScreenContainer } from '../components/ScreenContainer';
import { GlassCard } from '../components/GlassCard';
import { COLORS } from '../theme/colors';

export const RemindersScreen = () => {
  const [reminders, setReminders] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchReminders = async () => {
    setLoading(true);
    try {
      const data = await ApiService.getReminders();
      setReminders(data.reminders || []);
    } catch (err: any) {
      console.error(err);
      Alert.alert('Load Error', 'Failed to retrieve scheduled reminders.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReminders();
  }, []);

  const renderReminderItem = ({ item }: { item: any }) => {
    const nextRun = item.next_run_time
      ? new Date(item.next_run_time).toLocaleString([], {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })
      : 'Suspended / None';

    return (
      <GlassCard title={item.name || 'Job Entry'} borderColor={COLORS.primary}>
        <View style={styles.row}>
          <Text style={styles.label}>JOB ID</Text>
          <Text style={styles.value}>{item.id}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>NEXT RUN</Text>
          <Text style={[styles.value, item.next_run_time ? { color: COLORS.primary } : { color: COLORS.textMuted }]}>
            {nextRun}
          </Text>
        </View>
      </GlassCard>
    );
  };

  return (
    <ScreenContainer>
      {loading && reminders.length === 0 ? (
        <ActivityIndicator color={COLORS.primary} style={styles.loader} />
      ) : (
        <FlatList
          data={reminders}
          keyExtractor={(item) => item.id}
          renderItem={renderReminderItem}
          onRefresh={fetchReminders}
          refreshing={loading}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No active scheduled reminders.</Text>
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
  row: {
    flexDirection: 'row',
    marginVertical: 4,
    alignItems: 'center',
  },
  label: {
    color: COLORS.textMuted,
    fontSize: 9,
    fontWeight: 'bold',
    width: 90,
    letterSpacing: 1.5,
  },
  value: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '600',
  },
  emptyText: {
    color: COLORS.textMuted,
    textAlign: 'center',
    paddingVertical: 30,
    fontSize: 13,
  },
});
