import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListsApi } from '../../api/build_lists';
import { buildLogsApi } from '../../api/build_logs';
import type {
  BuildListRead,
  BuildLogPostRead,
  BuildLogReadPaginated,
} from '../../types/Api';

import ImageUpload from '../../components/forms/ImageUpload';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import Pagination from '../../components/ui/pagination';
import Spinner from '../../components/ui/spinner';
import { Textarea } from '../../components/ui/textarea';
import { BUILD_LOG_POSTS_PER_PAGE } from '../../constants';

const fetchBuildLogRequestFn = (buildListId: string, page: number = 1) => {
  const skip = (page - 1) * BUILD_LOG_POSTS_PER_PAGE;
  return buildLogsApi.getBuildLogByBuildList(
    buildListId,
    skip,
    BUILD_LOG_POSTS_PER_PAGE
  );
};

const fetchBuildListRequestFn = (buildListId: string) =>
  buildListsApi.getBuildList(buildListId);

function ViewBuildLog() {
  const { buildListId } = useParams<{ buildListId: string }>();
  const { user: currentUser } = useAuth();

  const [buildList, setBuildList] = useState<BuildListRead | null>(null);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [postToDelete, setPostToDelete] = useState<BuildLogPostRead | null>(
    null
  );
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [postToEdit, setPostToEdit] = useState<BuildLogPostRead | null>(null);
  const [editContent, setEditContent] = useState('');
  const editTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newPostContent, setNewPostContent] = useState('');
  const createTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const fetchBuildLogWithPage = useCallback(
    (buildListId: string) => {
      return fetchBuildLogRequestFn(buildListId, currentPage);
    },
    [currentPage]
  );

  const buildLogResponse = useApiRequest(fetchBuildLogWithPage);
  const buildLog = buildLogResponse.data as BuildLogReadPaginated | undefined;
  const isLoadingBuildLog = buildLogResponse.isLoading;
  const buildLogError = buildLogResponse.error;
  const fetchBuildLog = buildLogResponse.executeRequest;

  const {
    data: buildListData,
    isLoading: isLoadingBuildList,
    executeRequest: fetchBuildList,
  } = useApiRequest(fetchBuildListRequestFn);

  useEffect(() => {
    if (buildListId) {
      void fetchBuildLog(buildListId);
      void fetchBuildList(buildListId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildListId, currentPage]);

  useEffect(() => {
    if (buildListData) {
      setBuildList(buildListData);
    }
  }, [buildListData]);

  const handleCreatePost = async () => {
    if (!buildListId || !newPostContent.trim()) return;

    try {
      await buildLogsApi.createBuildLogPost(buildListId, {
        content: newPostContent.trim(),
      });
      setNewPostContent('');
      setIsCreateDialogOpen(false);
      // Reset to first page after creating a post - this will trigger useEffect to refetch
      if (currentPage !== 1) {
        setCurrentPage(1);
      } else if (buildListId) {
        // If already on page 1, manually refetch
        void fetchBuildLog(buildListId);
      }
    } catch (error) {
      console.error('Failed to create post:', error);
    }
  };

  const handleEditPost = async () => {
    if (!buildListId || !postToEdit || !editContent.trim()) return;

    try {
      await buildLogsApi.updateBuildLogPost(postToEdit.id, {
        content: editContent.trim(),
      });
      setIsEditDialogOpen(false);
      setPostToEdit(null);
      setEditContent('');
      void fetchBuildLog(buildListId);
    } catch (error) {
      console.error('Failed to update post:', error);
    }
  };

  const handleDeletePost = async () => {
    if (!buildListId || !postToDelete) return;

    try {
      await buildLogsApi.deleteBuildLogPost(postToDelete.id);
      setIsDeleteConfirmOpen(false);
      setPostToDelete(null);
      // If we deleted the last post on the page and it's not page 1, go to previous page
      // This will trigger useEffect to refetch
      if (buildLog && buildLog.posts.length === 1 && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else if (buildListId) {
        // Otherwise just refetch current page
        void fetchBuildLog(buildListId);
      }
    } catch (error) {
      console.error('Failed to delete post:', error);
    }
  };

  const openEditDialog = (post: BuildLogPostRead) => {
    setPostToEdit(post);
    setEditContent(post.content);
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (post: BuildLogPostRead) => {
    setPostToDelete(post);
    setIsDeleteConfirmOpen(true);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const insertImageMarkdown = (
    imageUrl: string,
    textareaRef: React.RefObject<HTMLTextAreaElement | null>,
    contentSetter: (value: string) => void,
    currentContent: string
  ) => {
    const textarea = textareaRef.current;
    if (!textarea) {
      // If no textarea ref, just append to the end
      contentSetter(currentContent + `\n\n![Image](${imageUrl})\n`);
      return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const textBefore = currentContent.substring(0, start);
    const textAfter = currentContent.substring(end);
    const imageMarkdown = `![Image](${imageUrl})`;

    // Insert image markdown at cursor position, or at end if no selection
    const newContent = textBefore + imageMarkdown + textAfter;
    contentSetter(newContent);

    // Set cursor position after the inserted image markdown
    setTimeout(() => {
      const newCursorPos = start + imageMarkdown.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
      textarea.focus();
    }, 0);
  };

  const handleImageUploaded = (_fileKey: string, presignedUrl: string) => {
    // Insert image markdown into the create post textarea
    insertImageMarkdown(
      presignedUrl,
      createTextareaRef,
      setNewPostContent,
      newPostContent
    );
  };

  const handleEditImageUploaded = (_fileKey: string, presignedUrl: string) => {
    // Insert image markdown into the edit post textarea
    insertImageMarkdown(
      presignedUrl,
      editTextareaRef,
      setEditContent,
      editContent
    );
  };

  if (isLoadingBuildLog || isLoadingBuildList) {
    return (
      <>
        <PageHeader title="Build Log" />
        <Spinner />
      </>
    );
  }

  if (buildLogError) {
    return (
      <div>
        <PageHeader title="Build Log" />
        <Card>
          <ErrorAlert message={`Failed to load build log. ${buildLogError}`} />
        </Card>
      </div>
    );
  }

  if (!buildLog) {
    return (
      <div>
        <PageHeader title="Build Log" />
        <Card>
          <ErrorAlert
            message={`Build log for build list "${buildListId}" not found.`}
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={
          buildList
            ? buildList.name
            : (buildLog?.title || '').replace('Build Log: ', '')
        }
      />
      {buildList && (
        <div className="mb-4">
          <Link
            to={`/build-lists/${buildList.id}`}
            className="text-info hover:text-info/90 underline"
          >
            ← Back to Build List
          </Link>
        </div>
      )}

      <Card className="mb-6">
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Build Log Thread" />
          {currentUser && (
            <Button
              type="button"
              onClick={() => setIsCreateDialogOpen(true)}
              className="bg-info hover:bg-info/90 text-white"
            >
              New Post
            </Button>
          )}
        </div>

        {buildLog && buildLog.posts.length === 0 ? (
          <div className="text-center py-12 text-foreground">
            <p className="text-lg mb-2">No posts yet.</p>
            <p className="text-sm text-muted-foreground">
              {currentUser
                ? 'Be the first to post in this build log!'
                : 'Log in to post in this build log.'}
            </p>
          </div>
        ) : buildLog ? (
          <>
            {/* Pagination at top */}
            {'pagination' in buildLog &&
              buildLog.pagination &&
              buildLog.pagination.total_pages > 1 && (
                <div className="mb-6">
                  <Pagination
                    currentPage={buildLog.pagination.current_page}
                    totalPages={buildLog.pagination.total_pages}
                    onPageChange={(page) => {
                      setCurrentPage(page);
                      // Scroll to top when page changes
                      window.scrollTo({ top: 0, behavior: 'smooth' });
                    }}
                    itemsPerPage={buildLog.pagination.items_per_page}
                    totalItems={buildLog.pagination.total_items}
                  />
                </div>
              )}

            <div className="space-y-4">
              {buildLog.posts.map((post: BuildLogPostRead) => {
                const canEdit = currentUser && currentUser.id === post.user_id;
                const canDelete =
                  currentUser &&
                  (currentUser.id === post.user_id ||
                    (buildList && currentUser.id === buildList.user_id));
                const isEdited = post.created_at !== post.updated_at;

                return (
                  <Card key={post.id} className="bg-muted/50">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          {post.author_image_url ? (
                            <img
                              src={post.author_image_url}
                              alt={post.author_username || 'User'}
                              className="w-10 h-10 rounded object-cover flex-shrink-0"
                            />
                          ) : (
                            <div className="w-10 h-10 rounded bg-muted flex items-center justify-center flex-shrink-0">
                              <span className="text-lg text-foreground">
                                {(post.author_username || 'U')
                                  .charAt(0)
                                  .toUpperCase()}
                              </span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-info">
                              {post.author_username || 'Unknown User'}
                            </span>
                            <span className="text-muted-foreground text-sm">
                              {formatDate(post.created_at)}
                            </span>
                            {isEdited && (
                              <span className="text-muted-foreground text-xs italic">
                                (edited)
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-foreground prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown
                            components={{
                              p: ({ children }) => (
                                <p className="mb-2 last:mb-0 text-foreground">
                                  {children}
                                </p>
                              ),
                              h1: ({ children }) => (
                                <h1 className="text-2xl font-bold mb-2 mt-4 first:mt-0 text-foreground">
                                  {children}
                                </h1>
                              ),
                              h2: ({ children }) => (
                                <h2 className="text-xl font-bold mb-2 mt-4 first:mt-0 text-foreground">
                                  {children}
                                </h2>
                              ),
                              h3: ({ children }) => (
                                <h3 className="text-lg font-bold mb-2 mt-4 first:mt-0 text-foreground">
                                  {children}
                                </h3>
                              ),
                              ul: ({ children }) => (
                                <ul className="list-disc list-inside mb-2 space-y-1 text-foreground">
                                  {children}
                                </ul>
                              ),
                              ol: ({ children }) => (
                                <ol className="list-decimal list-inside mb-2 space-y-1 text-foreground">
                                  {children}
                                </ol>
                              ),
                              li: ({ children }) => (
                                <li className="ml-4 text-foreground">
                                  {children}
                                </li>
                              ),
                              code: ({ children, className }) => {
                                const isInline = !className;
                                return isInline ? (
                                  <code className="bg-muted px-1 py-0.5 rounded text-sm font-mono text-foreground">
                                    {children}
                                  </code>
                                ) : (
                                  <code className="block bg-muted p-2 rounded text-sm font-mono overflow-x-auto text-foreground">
                                    {children}
                                  </code>
                                );
                              },
                              pre: ({ children }) => (
                                <pre className="bg-muted p-2 rounded mb-2 overflow-x-auto text-foreground">
                                  {children}
                                </pre>
                              ),
                              blockquote: ({ children }) => (
                                <blockquote className="border-l-4 border-info pl-4 italic my-2 text-foreground">
                                  {children}
                                </blockquote>
                              ),
                              a: ({ href, children }) => (
                                <a
                                  href={href}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-info hover:text-info/90 underline"
                                >
                                  {children}
                                </a>
                              ),
                              img: ({ src, alt }) => (
                                <img
                                  src={src}
                                  alt={alt || 'Image'}
                                  className="max-w-full h-auto rounded-lg my-2"
                                />
                              ),
                              strong: ({ children }) => (
                                <strong className="font-bold text-foreground">
                                  {children}
                                </strong>
                              ),
                              em: ({ children }) => (
                                <em className="italic text-foreground">
                                  {children}
                                </em>
                              ),
                            }}
                          >
                            {post.content}
                          </ReactMarkdown>
                        </div>
                      </div>
                      {(canEdit || canDelete) && (
                        <div className="flex gap-2 ml-4">
                          {canEdit && (
                            <button
                              type="button"
                              onClick={() => openEditDialog(post)}
                              className="text-info hover:text-info/90 text-sm"
                            >
                              Edit
                            </button>
                          )}
                          {canDelete && (
                            <button
                              type="button"
                              onClick={() => openDeleteDialog(post)}
                              className="text-destructive hover:text-destructive/80 text-sm"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
            {'pagination' in buildLog &&
              buildLog.pagination &&
              buildLog.pagination.total_pages > 1 && (
                <Pagination
                  currentPage={buildLog.pagination.current_page}
                  totalPages={buildLog.pagination.total_pages}
                  onPageChange={(page) => {
                    setCurrentPage(page);
                    // Scroll to top when page changes
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  itemsPerPage={buildLog.pagination.items_per_page}
                  totalItems={buildLog.pagination.total_items}
                />
              )}
          </>
        ) : null}
      </Card>

      {/* Create Post Dialog */}
      {currentUser && (
        <Dialog
          open={isCreateDialogOpen}
          onOpenChange={(open) => {
            setIsCreateDialogOpen(open);
            if (!open) setNewPostContent('');
          }}
        >
          <DialogContent className="sm:max-w-4xl">
            <DialogHeader>
              <DialogTitle>New Post</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="post-content"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Post Content (Markdown supported)
                </label>
                <Textarea
                  id="post-content"
                  ref={createTextareaRef}
                  value={newPostContent}
                  onChange={(e) => setNewPostContent(e.target.value)}
                  className="font-mono"
                  rows={12}
                  placeholder="Share your build progress, ask questions, or provide updates...

Markdown examples:
**bold text**
*italic text*
# Heading
- List item
[Link text](https://example.com)
![Image](image-url)
`code`"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Markdown formatting is supported. Use **bold**, *italic*, #
                  headings, - lists, and more.
                </p>
              </div>
              <div>
                <ImageUpload
                  entityType="build_log_post"
                  entityId={buildListId ?? ''}
                  onImageUploaded={handleImageUploaded}
                  label="Upload Image"
                  maxSizeMB={10}
                  showPreview={false}
                  className="mb-2"
                />
                <p className="text-xs text-muted-foreground">
                  Upload an image and it will be inserted into your post as
                  markdown.
                </p>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setIsCreateDialogOpen(false);
                    setNewPostContent('');
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={() => void handleCreatePost()}
                  disabled={!newPostContent.trim()}
                  className="bg-info hover:bg-info/90 text-white"
                >
                  Post
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Edit Post Dialog */}
      {postToEdit && (
        <Dialog
          open={isEditDialogOpen}
          onOpenChange={(open) => {
            setIsEditDialogOpen(open);
            if (!open) {
              setPostToEdit(null);
              setEditContent('');
            }
          }}
        >
          <DialogContent className="sm:max-w-4xl">
            <DialogHeader>
              <DialogTitle>Edit Post</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="edit-content"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Post Content (Markdown supported)
                </label>
                <Textarea
                  id="edit-content"
                  ref={editTextareaRef}
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="font-mono"
                  rows={12}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Markdown formatting is supported. Use **bold**, *italic*, #
                  headings, - lists, and more.
                </p>
              </div>
              <div>
                <ImageUpload
                  entityType="build_log_post"
                  entityId={buildListId ?? ''}
                  onImageUploaded={handleEditImageUploaded}
                  label="Upload Image"
                  maxSizeMB={10}
                  showPreview={false}
                  className="mb-2"
                />
                <p className="text-xs text-muted-foreground">
                  Upload an image and it will be inserted into your post as
                  markdown.
                </p>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setIsEditDialogOpen(false);
                    setPostToEdit(null);
                    setEditContent('');
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={() => void handleEditPost()}
                  disabled={!editContent.trim()}
                  className="bg-info hover:bg-info/90 text-white"
                >
                  Save
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Delete Confirmation Dialog */}
      {postToDelete && (
        <ConfirmDialog
          open={isDeleteConfirmOpen}
          onOpenChange={(open) => {
            setIsDeleteConfirmOpen(open);
            if (!open) setPostToDelete(null);
          }}
          onConfirm={() => void handleDeletePost()}
          title="Confirm Deletion"
          description={
            <>
              Are you sure you want to delete this post? This action cannot be
              undone.
            </>
          }
          confirmLabel="Confirm Delete"
          loadingLabel="Deleting..."
          variant="destructive"
        />
      )}
    </div>
  );
}

export default ViewBuildLog;
