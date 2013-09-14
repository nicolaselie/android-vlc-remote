/*-
 *  Copyright (C) 2009 Peter Baldwin   
 *  
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

package org.peterbaldwin.vlcremote.model;

import android.content.Intent;
import android.net.Uri;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.peterbaldwin.vlcremote.util.MimeTypeMap;

public final class File {
    
    public static final int PATH_UNIX = 0;
    public static final int PATH_WINDOWS = 1;
    public static int PATH_TYPE = PATH_UNIX;

    private static final MimeTypeMap sMimeTypeMap = MimeTypeMap.getSingleton();

    private static String parseExtension(String path) {
        int index = path.lastIndexOf('.');
        if (index != -1) {
            return path.substring(index + 1);
        } else {
            return null;
        }
    }
    
    public static String baseName(String path) {
        if(path == null) {
            return null;
        }
        String fileProtocol = "file:///";
        int offset = 0;
        if(path.startsWith(fileProtocol)) {
            offset = fileProtocol.length();
        }
        int bslash = path.lastIndexOf('\\');
        int fslash = path.substring(offset).lastIndexOf('/') + offset;
        if(fslash == -1 && bslash == -1) {
            return path;
        }
        return path.substring(Math.max(bslash, fslash) + 1);
    }

    private String mType;
    private Long mSize;
    private String mDate;
    private String mPath;
    private String mName;
    private String mExtension;

    public File(String type, Long size, String date, String path, String name, String extension) {
        mType = type;
        mSize = size;
        mDate = date;
        mPath = path;
        mName = name;
        mExtension = extension != null ? extension : path != null ? parseExtension(path) : null;
    }

    public String getType() {
        return mType;
    }

    public void setType(String type) {
        mType = type;
    }

    public boolean isDirectory() {
        // Type is "directory" in VLC 1.0 and "dir" in VLC 1.1
        return "directory".equals(mType) || "dir".equals(mType);
    }
    
    /**
     * Checks if this File is a parent entry (name is ..)
     * @return true if this File is a parent entry, false otherwise. 
     */
    public boolean isParent() {
        return "..".equals(mName);
    }

    public boolean isImage() {
        String mimeType = getMimeType();
        return mimeType != null && mimeType.startsWith("image/");
    }

    public Long getSize() {
        return mSize;
    }

    public void setSize(Long size) {
        mSize = size;
    }

    public String getDate() {
        return mDate;
    }

    public void setDate(String date) {
        mDate = date;
    }

    public String getPath() {
        return mPath;
    }
    
    public String getNormalizedPath() {
        return getNormalizedPath(mPath);
    }
    
    /**
     * Get the normalized path for the given file path.
     * Any parent directories (..) will be resolved.
     * @param file file path
     * @return 
     */
    public static String getNormalizedPath(String file) {
        String[] st = file.split("(\\\\|/)+");
        ArrayDeque<String> segmentList = new ArrayDeque<String>();
        for(String segment : st) {
            if("..".equals(segment)) {
                segmentList.pollFirst();
                continue;
            }
            segmentList.offerFirst(segment);
        }
        if(segmentList.isEmpty()) {
            return Directory.ROOT_DIRECTORY;
        }
        StringBuilder sb = new StringBuilder();
        while(!segmentList.isEmpty()) {
            sb.append(segmentList.pollLast());
            if(segmentList.peekLast() != null) {
                sb.append('/');
            }
        }
        return sb.length() == 0 ? Directory.ROOT_DIRECTORY : sb.toString();
    }

    public String getMrl() {
        if (isImage()) {
            return "fake://";
        } else {
            java.io.File file = new java.io.File(mPath);
            Uri uri = Uri.fromFile(file);
            return uri.toString();
        }
    }

    public List<String> getOptions() {
        if (isImage()) {
            return Collections.singletonList(":fake-file=" + getPath());
        } else {
            return Collections.emptyList();
        }
    }

    public List<String> getStreamingOptions() {
        List<String> options = new ArrayList<String>(getOptions());
        String mimeType = getMimeType();
        if (mimeType != null && mimeType.startsWith("audio/")) {
            options.add("#transcode{acodec=mp3,ab=128}");
        } else {
            options.add("#transcode{vcodec=mp4v,vb=384,acodec=mp4a,ab=64,channels=2,fps=25,venc=x264{profile=baseline,keyint=50,bframes=0,no-cabac,ref=1,vbv-maxrate=4096,vbv-bufsize=1024,aq-mode=0,no-mbtree,partitions=none,no-weightb,weightp=0,me=dia,subme=0,no-mixed-refs,no-8x8dct,trellis=0,level1.3},vfilter=canvas{width=320,height=180,aspect=320:180,padd},senc,soverlay}");
        }
        return options;
    }

    public Intent getIntentForStreaming(String authority) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        String mimeType = getMimeType();
        Uri.Builder builder = new Uri.Builder();
        builder.scheme("rtsp");
        builder.encodedAuthority(swapPortNumber(authority, 8554));
        builder.path("stream.sdp");
        Uri data = builder.build();
        
        if (mimeType != null && mimeType.startsWith("audio/")) {
            intent.setDataAndType(data, "audio/mp3");
        } else if (mimeType != null && mimeType.startsWith("video/")) {
            intent.setDataAndType(data, "video/mp4");
        } else {
            intent.setData(data);
        }
        return intent;
    }

    public void setPath(String path) {
        mPath = path;
        if (mExtension == null && path != null) {
            mExtension = parseExtension(path);
        }
    }

    public String getName() {
        return mName;
    }

    public void setName(String name) {
        mName = name;
    }

    public String getExtension() {
        return mExtension;
    }

    public void setExtension(String extension) {
        mExtension = extension;
    }

    public String getMimeType() {
        if (mExtension != null) {
            // See http://code.google.com/p/android/issues/detail?id=8806
            String extension = mExtension.toLowerCase();
            return sMimeTypeMap.getMimeTypeFromExtension(extension);
        } else {
            return null;
        }
    }

    @Override
    public String toString() {
        return mName;
    }

    private static String removePortNumber(String authority) {
        int index = authority.lastIndexOf(':');
        if (index != -1) {
            // Remove port number
            authority = authority.substring(0, index);
        }
        return authority;
    }

    private static String swapPortNumber(String authority, int port) {
        return removePortNumber(authority) + ":" + port;
    }
}
