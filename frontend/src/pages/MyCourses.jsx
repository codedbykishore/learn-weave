import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaQuery } from '@mantine/hooks';
import {
  Container,
  Title,
  Text,
  Grid,
  Card,
  Image,
  Button,
  Group,
  Loader,
  Alert,
  useMantineTheme,
  Box,
  TextInput,
  Paper,
  Stack,
  ActionIcon,
  Modal,
  Textarea,
  Switch,
  rem,
  Progress,
  Badge,
} from '@mantine/core';
import SearchBar from '../components/SearchBar';
import { 
  IconBook, 
  IconAlertCircle, 
  IconWorld, 
  IconSearch, 
  IconPencil, 
  IconTrash, 
  IconCheck,
  IconLoader,
  IconFlame,
  IconClock
} from '@tabler/icons-react';
import courseService from '../api/courseService';
import { useTranslation } from 'react-i18next';
import PlaceGolderImage from '../assets/place_holder_image.png';

function MyCourses() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredCourses, setFilteredCourses] = useState([]);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [courseToDeleteId, setCourseToDeleteId] = useState(null);
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [courseToRename, setCourseToRename] = useState(null);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  
  const navigate = useNavigate();
  const theme = useMantineTheme();
  const { t } = useTranslation('dashboard');

  // Helper function to get status badge color and icon
  const getStatusInfo = (status) => {
    const label = t(`status.${status?.replace(/^.*\./, '').toLowerCase()}`, { defaultValue: status });

    switch (status) {
      case 'CourseStatus.CREATING':
        return { label, color: 'yellow', Icon: IconLoader };
      case 'CourseStatus.FINISHED':
      case 'CourseStatus.COMPLETED':
        return { label, color: 'green', Icon: IconCheck };
      case 'CourseStatus.FAILED':
        return { label, color: 'red', Icon: IconAlertCircle };
      default:
        return { label, color: 'gray', Icon: IconBook };
    }
  };

  // Calculate progress for a course
  const calculateProgress = (course) => {
    if (course.status === 'CourseStatus.COMPLETED') return 100;
    if (course.status === 'CourseStatus.CREATING') return 0;
    return (course?.chapter_count > 0)
      ? Math.round((100 * (course.completed_chapter_count || 0)) / course.chapter_count)
      : 0;
  };

  // Fetch user's courses
  useEffect(() => {
    const fetchCourses = async () => {
      try {
        setLoading(true);
        const coursesData = await courseService.getUserCourses();
        setCourses(coursesData);
        setError(null);
      } catch (err) {
        setError(t('loadCoursesError'));
        console.error('Error fetching courses:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCourses();
  }, [t]);

  // Update filtered courses when search query or courses change
  useEffect(() => {
    if (!searchQuery) {
      setFilteredCourses(courses);
    } else {
      const query = searchQuery.toLowerCase().trim();
      const filtered = courses.filter(course => {
        const title = (course.title || '').toLowerCase();
        const description = (course.description || '').toLowerCase();
        return title.includes(query) || description.includes(query);
      });
      setFilteredCourses(filtered);
    }
  }, [searchQuery, courses]);

  // Handle course deletion
  const handleDelete = (courseId) => {
    setCourseToDeleteId(courseId);
    setDeleteModalOpen(true);
  };

  const confirmDeleteHandler = async () => {
    if (!courseToDeleteId) return;
    try {
      await courseService.deleteCourse(courseToDeleteId);
      setCourses(prevCourses => prevCourses.filter(course => course.course_id !== courseToDeleteId));
      setDeleteModalOpen(false);
    } catch (err) {
      setError(t('errors.deleteCourse', { message: err.message || '' }));
      console.error('Error deleting course:', err);
    }
  };

  // Handle course renaming
  const handleRename = (course) => {
    setCourseToRename(course);
    setNewTitle(course.title || '');
    setNewDescription(course.description || '');
    setIsPublic(course.is_public || false);
    setRenameModalOpen(true);
  };

  const confirmRenameHandler = async () => {
    if (!courseToRename) return;
    try {
      // First, update the public status
      await courseService.updateCoursePublicStatus(courseToRename.course_id, isPublic);

      // Then, update the title and description
      const updatedCourse = await courseService.updateCourse(
        courseToRename.course_id, 
        newTitle, 
        newDescription
      );

      // Combine updates for the UI
      const finalUpdatedCourse = { ...updatedCourse, is_public: isPublic };

      setCourses(prevCourses =>
        prevCourses.map(course =>
          course.course_id === courseToRename.course_id ? finalUpdatedCourse : course
        )
      );
      setRenameModalOpen(false);
    } catch (err) {
      setError(t('errors.renameCourse', { message: err.message || '' }));
      console.error('Error updating course:', err);
    }
  };

  if (loading) {
    return (
      <Container 
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '50vh',
          textAlign: 'center',
          gap: '1rem'
        }}
      >
        <Loader size="xl" variant="dots" />
        <Text size="lg" color="dimmed">
          {t('loadingMyCourses', { ns: 'dashboard', defaultValue: 'Loading your courses...' })}
        </Text>
      </Container>
    );
  }

  if (error) {
    return (
      <Container style={{ paddingTop: '20px' }}>
        <Alert icon={<IconAlertCircle size={16} />} title={t('errorTitle')} color="red">
          {error}
        </Alert>
      </Container>
    );
  }

  return (
    <Container size="lg" py="xl">
      <Box
        pb="xl"
        mb="xl"
        style={{
          borderBottom: `1px solid ${
            theme.colorScheme === 'dark' ? theme.colors.dark[5] : theme.colors.gray[2]
          }`,
        }}
      >
        <Group position="apart">
          <div>
            <Title order={2}>{t('myCoursesTitle', { defaultValue: 'My Courses' })}</Title>
            <Text color="dimmed" mt={4}>
              {t('myCoursesSubtitle', { defaultValue: 'Manage and browse your personal courses.' })}
            </Text>
          </div>
          <IconBook size={40} color={theme.colors.blue[5]} stroke={1.5} />
        </Group>
      </Box>

      <TextInput
        placeholder={t('searchMyCoursesPlaceholder', { ns: 'dashboard', defaultValue: 'Search courses...' })}
        value={searchQuery}
        onChange={(event) => setSearchQuery(event.currentTarget.value)}
        icon={<IconSearch size={16} />}
        mb="xl"
      />

      {filteredCourses.length === 0 && !loading ? (
        <Paper withBorder radius="md" p="xl" mt="xl" bg={theme.colorScheme === 'dark' ? theme.colors.dark[6] : theme.colors.gray[0]}>
          <Stack align="center" spacing="md" py="xl">
            <IconBook size={60} color={theme.colors.gray[6]} stroke={1.5} />
            <Title order={3} align="center">
              {searchQuery 
                ? t('noSearchResults', { defaultValue: 'No courses found' }) 
                : t('noCoursesYet', { defaultValue: 'No courses yet' })}
            </Title>
            <Text color="dimmed" size="sm" align="center">
              {searchQuery 
                ? t('tryDifferentKeywords', { defaultValue: 'Try different search terms.' }) 
                : t('createFirstCourse', { defaultValue: 'Create your first course to get started.' })}
            </Text>
            {!searchQuery && (
              <Button 
                leftIcon={<IconFlame size={16} />} 
                onClick={() => navigate('/create-course')}
                mt="md"
              >
                {t('createCourseButton', { defaultValue: 'Create Course' })}
              </Button>
            )}
          </Stack>
        </Paper>
      ) : (
        <Grid gutter="xl">
          {filteredCourses.map((course) => {
            const { label: statusLabel, color: statusColor, Icon: StatusIcon } = getStatusInfo(course.status);
            const progress = calculateProgress(course);
            
            return (
              <Grid.Col key={course.course_id} sm={6} md={4} lg={4}>
                <Card 
                  shadow="sm" 
                  p="lg" 
                  radius="md" 
                  withBorder
                  style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
                  sx={{
                    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                    '&:hover': {
                      transform: 'translateY(-5px)',
                      boxShadow: theme.shadows.lg,
                    },
                  }}
                >
                  <Card.Section>
                    <Image
                      src={course.image_url || PlaceGolderImage}
                      height={160}
                      alt={course.title}
                      withPlaceholder
                      style={{
                        objectFit: 'cover',
                        width: '100%',
                        height: '160px'
                      }}
                    />
                  </Card.Section>

                  <Group position="apart" mt="md" mb="xs">
                    <Badge 
                      color={statusColor} 
                      variant="light"
                      leftSection={<StatusIcon size={14} style={{ marginTop: 2 }} />}
                    >
                      {statusLabel}
                    </Badge>
                    <Group spacing="xs">
                      <ActionIcon 
                        variant="subtle" 
                        color="gray" 
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRename(course);
                        }}
                      >
                        <IconPencil size={16} />
                      </ActionIcon>
                      
                      <ActionIcon 
                        variant="subtle" 
                        color="red" 
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(course.course_id);
                        }}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Group>
                  
                  <Text weight={500} lineClamp={2} mt="xs" mb="sm" style={{ minHeight: '3em' }}>
                    {course.title || t('untitledCourse', { defaultValue: 'Untitled Course' })}
                  </Text>

                  <Text size="sm" color="dimmed" lineClamp={3} style={{ flexGrow: 1, marginBottom: '1rem' }}>
                    {course.description || t('noDescription', { defaultValue: 'No description' })}
                  </Text>

                  <Box mb="md">
                    <Group position="apart" mb={5}>
                      <Text size="sm" color="dimmed">
                        {t('progress', { defaultValue: 'Progress' })}
                      </Text>
                      <Text size="sm" weight={500}>
                        {progress}%
                      </Text>
                    </Group>
                    <Progress value={progress} size="sm" radius="xl" />
                  </Box>

                  <Button 
                    fullWidth 
                    variant="filled"
                    color="teal" 
                    mt="md"
                    onClick={() => navigate(`/dashboard/courses/${course.course_id}`)}
                    leftIcon={<IconBook size={16} />}
                  >
                    {t('openCourse', { defaultValue: 'Open' })}
                  </Button>
                </Card>
              </Grid.Col>
            );
          })}
        </Grid>
      )}

      {/* Delete Confirmation Modal */}
      <Modal
        opened={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title={t('deleteModal.title', { defaultValue: 'Delete Course' })}
        centered
      >
        <Text>{t('deleteModal.confirmation', { defaultValue: 'Are you sure you want to delete this course? This action cannot be undone.' })}</Text>
        <Group position="right" mt="md">
          <Button variant="default" onClick={() => setDeleteModalOpen(false)}>
            {t('cancel', { defaultValue: 'Cancel' })}
          </Button>
          <Button color="red" onClick={confirmDeleteHandler}>
            {t('delete', { defaultValue: 'Delete' })}
          </Button>
        </Group>
      </Modal>

      {/* Rename Course Modal */}
      <Modal
        opened={renameModalOpen}
        onClose={() => setRenameModalOpen(false)}
        title={t('renameModal.title', { defaultValue: 'Edit Course' })}
        size="lg"
      >
        <Stack spacing="md">
          <TextInput
            label={t('title', { defaultValue: 'Title' })}
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            required
          />
          
          <Textarea
            label={t('description', { defaultValue: 'Beschreibung' })}
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            minRows={3}
          />
          
          <Switch
            label={t('publicCourse', { defaultValue: 'Publicly visible' })}
            checked={isPublic}
            onChange={(e) => setIsPublic(e.currentTarget.checked)}
            description={t('publicCourseDescription', { 
              defaultValue: 'Other users can find and access this course.' 
            })}
          />
          
          <Group position="right" mt="md">
            <Button variant="default" onClick={() => setRenameModalOpen(false)}>
              {t('cancel', { defaultValue: 'Cancel' })}
            </Button>
            <Button onClick={confirmRenameHandler}>
              {t('saveChanges', { defaultValue: 'Save Changes' })}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}

export default MyCourses;
